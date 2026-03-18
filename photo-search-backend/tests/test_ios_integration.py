#!/usr/bin/env python3
import os
import sys
import json
import time
import asyncio
import httpx
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_IMAGE_DIR = Path(os.getenv("TEST_IMAGE_DIR", "tests/test_images"))


@dataclass
class TestResult:
    name: str
    success: bool
    duration_ms: float
    message: str
    details: Optional[Dict] = None


class IOSClientSimulator:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        self.uploaded_images: List[str] = []
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
            
    async def health_check(self) -> TestResult:
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                return TestResult(
                    name="Health Check",
                    success=True,
                    duration_ms=duration,
                    message="Service is running",
                    details=data
                )
            else:
                return TestResult(
                    name="Health Check",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name="Health Check",
                success=False,
                duration_ms=duration,
                message=str(e)
            )
    
    async def upload_single_image(self, image_path: Path) -> TestResult:
        start = time.time()
        try:
            with open(image_path, 'rb') as f:
                files = {'file': (image_path.name, f, 'image/jpeg')}
                resp = await self.client.post(
                    f"{self.base_url}/api/v1/images/upload",
                    files=files
                )
            
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                image_id = result.get('id')
                if image_id:
                    self.uploaded_images.append(image_id)
                
                return TestResult(
                    name=f"Upload Image: {image_path.name}",
                    success=True,
                    duration_ms=duration,
                    message=f"Upload successful, ID: {image_id}",
                    details=result
                )
            else:
                return TestResult(
                    name=f"Upload Image: {image_path.name}",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=f"Upload Image: {image_path.name}",
                success=False,
                duration_ms=duration,
                message=str(e)
            )
    
    async def upload_multiple_images(self, image_dir: Path) -> List[TestResult]:
        results = []
        
        if not image_dir.exists():
            return [TestResult(
                name="Batch Upload",
                success=False,
                duration_ms=0,
                message=f"Test image directory not found: {image_dir}"
            )]
        
        image_files = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
        
        if not image_files:
            return [TestResult(
                name="Batch Upload",
                success=False,
                duration_ms=0,
                message=f"No .jpg or .png images found in {image_dir}"
            )]
        
        print(f"    Found {len(image_files)} test images")
        
        for image_path in image_files[:5]:
            result = await self.upload_single_image(image_path)
            results.append(result)
            await asyncio.sleep(0.5)
            
        return results
    
    async def text_search(self, query: str, top_k: int = 5) -> TestResult:
        start = time.time()
        try:
            payload = {"query": query, "top_k": top_k}
            
            resp = await self.client.post(
                f"{self.base_url}/api/v1/search/text",
                json=payload
            )
            
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                result_count = len(result.get('results', []))
                
                return TestResult(
                    name=f"Text Search: '{query}'",
                    success=True,
                    duration_ms=duration,
                    message=f"Found {result_count} results",
                    details=result
                )
            else:
                return TestResult(
                    name=f"Text Search: '{query}'",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=f"Text Search: '{query}'",
                success=False,
                duration_ms=duration,
                message=str(e)
            )
    
    async def similar_image_search(self, image_id: str, top_k: int = 5) -> TestResult:
        start = time.time()
        try:
            payload = {"image_id": image_id, "top_k": top_k}
            
            resp = await self.client.post(
                f"{self.base_url}/api/v1/search/similar",
                json=payload
            )
            
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                result_count = len(result.get('results', []))
                
                return TestResult(
                    name=f"Similar Search: {image_id[:8]}...",
                    success=True,
                    duration_ms=duration,
                    message=f"Found {result_count} similar images",
                    details=result
                )
            else:
                return TestResult(
                    name=f"Similar Search: {image_id[:8]}...",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=f"Similar Search: {image_id[:8]}...",
                success=False,
                duration_ms=duration,
                message=str(e)
            )
    
    async def get_image_info(self, image_id: str) -> TestResult:
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/images/{image_id}")
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                return TestResult(
                    name=f"Get Image Info: {image_id[:8]}...",
                    success=True,
                    duration_ms=duration,
                    message=f"Image: {result.get('filename', 'unknown')}",
                    details=result
                )
            elif resp.status_code == 404:
                return TestResult(
                    name=f"Get Image Info: {image_id[:8]}...",
                    success=False,
                    duration_ms=duration,
                    message="Image not found"
                )
            else:
                return TestResult(
                    name=f"Get Image Info: {image_id[:8]}...",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name=f"Get Image Info: {image_id[:8]}...",
                success=False,
                duration_ms=duration,
                message=str(e)
            )
    
    async def search_stats(self) -> TestResult:
        start = time.time()
        try:
            resp = await self.client.get(f"{self.base_url}/api/v1/search/stats")
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                return TestResult(
                    name="Search Stats",
                    success=True,
                    duration_ms=duration,
                    message=f"Total searches: {result.get('total_searches', 0)}",
                    details=result
                )
            else:
                return TestResult(
                    name="Search Stats",
                    success=False,
                    duration_ms=duration,
                    message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return TestResult(
                name="Search Stats",
                success=False,
                duration_ms=duration,
                message=str(e)
            )


class TestReporter:
    def __init__(self):
        self.results: List[TestResult] = []
        
    def add_result(self, result: TestResult):
        self.results.append(result)
        
    def add_results(self, results: List[TestResult]):
        self.results.extend(results)
        
    def print_summary(self):
        print("\n" + "="*70)
        print("iOS Client Integration Test Report")
        print("="*70)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"API URL: {API_BASE_URL}")
        print("-"*70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "N/A")
        print("-"*70)
        
        print("\nDetailed Results:")
        for i, result in enumerate(self.results, 1):
            status = "PASS" if result.success else "FAIL"
            print(f"\n{i}. [{status}] {result.name}")
            print(f"   Duration: {result.duration_ms:.2f}ms")
            print(f"   Result: {result.message}")
            
            if result.details and result.success:
                if 'results' in result.details:
                    print(f"   Data: {len(result.details['results'])} results")
                elif 'id' in result.details:
                    print(f"   Data: ID={result.details['id'][:8]}...")
        
        print("\n" + "="*70)
        
    def export_json(self, filename: str = "tests/test_report.json"):
        report = {
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success)
            },
            "results": [
                {
                    "name": r.name,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "message": r.message,
                    "details": r.details
                }
                for r in self.results
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\nTest report saved: {filename}")


async def run_all_tests():
    reporter = TestReporter()
    
    async with IOSClientSimulator() as client:
        print("\nStarting iOS Client Simulation Tests...")
        print("-"*70)
        
        print("\n1. Testing service health...")
        result = await client.health_check()
        reporter.add_result(result)
        
        if not result.success:
            print("Service unavailable, stopping tests")
            reporter.print_summary()
            return
        
        print(f"   Service OK")
        
        print("\n2. Testing batch image upload...")
        print(f"   Looking for test images in: {TEST_IMAGE_DIR}")
        results = await client.upload_multiple_images(TEST_IMAGE_DIR)
        reporter.add_results(results)
        
        if any(r.success for r in results):
            print(f"   Uploaded {sum(1 for r in results if r.success)} images")
        else:
            print(f"   Upload test failed or no test images found")
        
        print("\n3. Testing text search...")
        test_queries = ["节日", "风景", "人物", "建筑", "美食"]
        for query in test_queries:
            result = await client.text_search(query, top_k=3)
            reporter.add_result(result)
            if result.success:
                print(f"   '{query}': {result.message}")
            else:
                print(f"   '{query}': {result.message}")
            await asyncio.sleep(0.3)
        
        print("\n4. Testing similar image search...")
        if client.uploaded_images:
            for image_id in client.uploaded_images[:2]:
                result = await client.similar_image_search(image_id, top_k=3)
                reporter.add_result(result)
                if result.success:
                    print(f"   {image_id[:8]}...: {result.message}")
                else:
                    print(f"   {image_id[:8]}...: {result.message}")
                await asyncio.sleep(0.3)
        else:
            print("   No uploaded images available for testing")
        
        print("\n5. Testing get image info...")
        if client.uploaded_images:
            for image_id in client.uploaded_images[:2]:
                result = await client.get_image_info(image_id)
                reporter.add_result(result)
                if result.success:
                    print(f"   {image_id[:8]}...: {result.message}")
                else:
                    print(f"   {image_id[:8]}...: {result.message}")
        else:
            print("   No uploaded images available for testing")
        
        print("\n6. Testing search stats...")
        result = await client.search_stats()
        reporter.add_result(result)
        if result.success:
            print(f"   {result.message}")
        else:
            print(f"   {result.message}")
    
    reporter.print_summary()
    reporter.export_json()
    
    return reporter


if __name__ == "__main__":
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
