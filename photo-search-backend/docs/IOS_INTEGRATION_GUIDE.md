# iOS 客户端集成指南

本文档介绍如何在 iOS 应用中集成 Photo Search 后端服务，实现基于语义的多模态图片搜索功能。

## 目录

- [快速开始](#快速开始)
- [API 概览](#api-概览)
- [Swift 集成示例](#swift-集成示例)
- [核心功能实现](#核心功能实现)
- [错误处理](#错误处理)
- [最佳实践](#最佳实践)

## 快速开始

### 服务信息

- **API 基础 URL**: `http://localhost:8000` (开发环境)
- **API 版本**: v1
- **完整路径**: `http://localhost:8000/api/v1`

### 环境要求

- iOS 13.0+
- Swift 5.0+
- Xcode 12.0+

### 依赖库

```swift
// Package.swift
dependencies: [
    .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.6.0"),
    .package(url: "https://github.com/SDWebImage/SDWebImage.git", from: "5.0.0")
]
```

或使用 CocoaPods:

```ruby
pod 'Alamofire', '~> 5.6'
pod 'SDWebImage', '~> 5.0'
```

## API 概览

### 端点列表

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 服务健康检查 |
| `/api/v1/images/upload` | POST | 上传单张图片 |
| `/api/v1/images/{id}` | GET | 获取图片详情 |
| `/api/v1/search/text` | POST | 文本搜索图片 |
| `/api/v1/search/similar` | POST | 相似图片搜索 |
| `/api/v1/search/stats` | GET | 获取搜索统计 |

### 数据模型

#### ImageResponse

```swift
struct ImageResponse: Codable {
    let id: UUID
    let filename: String
    let width: Int?
    let height: Int?
    let fileSize: Int?
    let format: String?
    let originalUrl: String?
    let thumbnailUrl: String?
    let createdAt: Date
}
```

#### SearchResponse

```swift
struct SearchResponse: Codable {
    let query: String
    let results: [ImageSearchResult]
    let total: Int
    let searchTimeMs: Int?
}

struct ImageSearchResult: Codable {
    let image: ImageResponse
    let similarityScore: Double  // 0.0 - 1.0
}
```

## Swift 集成示例

### 1. 网络层封装

```swift
import Foundation
import Alamofire

class PhotoSearchAPI {
    static let shared = PhotoSearchAPI()
    private let baseURL = "http://localhost:8000"
    
    private init() {}
    
    // MARK: - Health Check
    
    func checkHealth(completion: @escaping (Result<HealthResponse, Error>) -> Void) {
        AF.request("\(baseURL)/health")
            .validate()
            .responseDecodable(of: HealthResponse.self) { response in
                completion(response.result.mapError { $0 as Error })
            }
    }
    
    // MARK: - Upload Image
    
    func uploadImage(_ image: UIImage, filename: String, completion: @escaping (Result<ImageResponse, Error>) -> Void) {
        guard let imageData = image.jpegData(compressionQuality: 0.9) else {
            completion(.failure(PhotoSearchError.invalidImage))
            return
        }
        
        AF.upload(
            multipartFormData: { multipartFormData in
                multipartFormData.append(
                    imageData,
                    withName: "file",
                    fileName: filename,
                    mimeType: "image/jpeg"
                )
            },
            to: "\(baseURL)/api/v1/images/upload"
        )
        .validate()
        .responseDecodable(of: ImageResponse.self) { response in
            completion(response.result.mapError { $0 as Error })
        }
    }
    
    // MARK: - Text Search
    
    func searchByText(query: String, topK: Int = 10, completion: @escaping (Result<SearchResponse, Error>) -> Void) {
        let parameters: [String: Any] = [
            "query": query,
            "top_k": topK
        ]
        
        AF.request(
            "\(baseURL)/api/v1/search/text",
            method: .post,
            parameters: parameters,
            encoding: JSONEncoding.default
        )
        .validate()
        .responseDecodable(of: SearchResponse.self) { response in
            completion(response.result.mapError { $0 as Error })
        }
    }
    
    // MARK: - Similar Image Search
    
    func searchSimilarImages(imageId: UUID, topK: Int = 10, completion: @escaping (Result<SearchResponse, Error>) -> Void) {
        let parameters: [String: Any] = [
            "image_id": imageId.uuidString,
            "top_k": topK
        ]
        
        AF.request(
            "\(baseURL)/api/v1/search/similar",
            method: .post,
            parameters: parameters,
            encoding: JSONEncoding.default
        )
        .validate()
        .responseDecodable(of: SearchResponse.self) { response in
            completion(response.result.mapError { $0 as Error })
        }
    }
    
    // MARK: - Get Image Info
    
    func getImageInfo(imageId: UUID, completion: @escaping (Result<ImageResponse, Error>) -> Void) {
        AF.request("\(baseURL)/api/v1/images/\(imageId.uuidString)")
            .validate()
            .responseDecodable(of: ImageResponse.self) { response in
                completion(response.result.mapError { $0 as Error })
            }
    }
}

// MARK: - Error Types

enum PhotoSearchError: Error {
    case invalidImage
    case networkError
    case serverError(String)
    case decodingError
}

// MARK: - Response Models

struct HealthResponse: Codable {
    let status: String
    let version: String
    let services: Services
    
    struct Services: Codable {
        let database: String
        let model: String
    }
}
```

### 2. 图片选择和上传

```swift
import UIKit
import PhotosUI

class UploadViewController: UIViewController {
    
    private let imagePicker = UIImagePickerController()
    
    override func viewDidLoad() {
        super.viewDidLoad()
        imagePicker.delegate = self
    }
    
    // 从相机拍照
    @IBAction func takePhotoTapped(_ sender: UIButton) {
        guard UIImagePickerController.isSourceTypeAvailable(.camera) else {
            showAlert(message: "相机不可用")
            return
        }
        imagePicker.sourceType = .camera
        present(imagePicker, animated: true)
    }
    
    // 从相册选择
    @IBAction func selectFromLibraryTapped(_ sender: UIButton) {
        var config = PHPickerConfiguration()
        config.selectionLimit = 5  // 最多选择5张
        config.filter = .images
        
        let picker = PHPickerViewController(configuration: config)
        picker.delegate = self
        present(picker, animated: true)
    }
    
    private func uploadImage(_ image: UIImage, filename: String) {
        PhotoSearchAPI.shared.uploadImage(image, filename: filename) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let imageResponse):
                    print("上传成功: \(imageResponse.id)")
                    self.showAlert(message: "上传成功!")
                case .failure(let error):
                    print("上传失败: \(error)")
                    self.showAlert(message: "上传失败: \(error.localizedDescription)")
                }
            }
        }
    }
    
    private func showAlert(message: String) {
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "确定", style: .default))
        present(alert, animated: true)
    }
}

// MARK: - UIImagePickerControllerDelegate

extension UploadViewController: UIImagePickerControllerDelegate, UINavigationControllerDelegate {
    func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey : Any]) {
        picker.dismiss(animated: true)
        
        guard let image = info[.originalImage] as? UIImage else { return }
        let filename = "camera_\(Int(Date().timeIntervalSince1970)).jpg"
        uploadImage(image, filename: filename)
    }
}

// MARK: - PHPickerViewControllerDelegate

extension UploadViewController: PHPickerViewControllerDelegate {
    func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
        picker.dismiss(animated: true)
        
        for (index, result) in results.enumerated() {
            result.itemProvider.loadObject(ofClass: UIImage.self) { [weak self] image, error in
                guard let image = image as? UIImage else { return }
                let filename = "library_\(index)_\(Int(Date().timeIntervalSince1970)).jpg"
                self?.uploadImage(image, filename: filename)
            }
        }
    }
}
```

### 3. 搜索功能实现

```swift
import UIKit
import SDWebImage

class SearchViewController: UIViewController {
    
    @IBOutlet weak var searchTextField: UITextField!
    @IBOutlet weak var collectionView: UICollectionView!
    
    private var searchResults: [ImageSearchResult] = []
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupCollectionView()
    }
    
    private func setupCollectionView() {
        collectionView.delegate = self
        collectionView.dataSource = self
        collectionView.register(ImageCell.self, forCellWithReuseIdentifier: "ImageCell")
    }
    
    @IBAction func searchButtonTapped(_ sender: UIButton) {
        guard let query = searchTextField.text, !query.isEmpty else {
            showAlert(message: "请输入搜索关键词")
            return
        }
        
        performSearch(query: query)
    }
    
    private func performSearch(query: String) {
        PhotoSearchAPI.shared.searchByText(query: query, topK: 20) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self?.searchResults = response.results
                    self?.collectionView.reloadData()
                    print("搜索完成，找到 \(response.total) 个结果，耗时 \(response.searchTimeMs ?? 0)ms")
                    
                case .failure(let error):
                    print("搜索失败: \(error)")
                    self?.showAlert(message: "搜索失败")
                }
            }
        }
    }
    
    private func searchSimilarImages(imageId: UUID) {
        PhotoSearchAPI.shared.searchSimilarImages(imageId: imageId, topK: 10) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self?.searchResults = response.results
                    self?.collectionView.reloadData()
                    
                case .failure(let error):
                    print("相似图片搜索失败: \(error)")
                }
            }
        }
    }
}

// MARK: - UICollectionViewDataSource

extension SearchViewController: UICollectionViewDataSource {
    func collectionView(_ collectionView: UICollectionView, numberOfItemsInSection section: Int) -> Int {
        return searchResults.count
    }
    
    func collectionView(_ collectionView: UICollectionView, cellForItemAt indexPath: IndexPath) -> UICollectionViewCell {
        let cell = collectionView.dequeueReusableCell(withReuseIdentifier: "ImageCell", for: indexPath) as! ImageCell
        let result = searchResults[indexPath.row]
        
        // 显示缩略图
        if let thumbnailUrl = result.image.thumbnailUrl {
            let fullUrl = "http://localhost:8000" + thumbnailUrl
            cell.imageView.sd_setImage(with: URL(string: fullUrl), placeholderImage: UIImage(systemName: "photo"))
        }
        
        // 显示相似度分数
        cell.similarityLabel.text = String(format: "%.2f", result.similarityScore)
        
        return cell
    }
}

// MARK: - UICollectionViewDelegate

extension SearchViewController: UICollectionViewDelegate {
    func collectionView(_ collectionView: UICollectionView, didSelectItemAt indexPath: IndexPath) {
        let result = searchResults[indexPath.row]
        
        // 跳转到图片详情页
        let detailVC = ImageDetailViewController()
        detailVC.imageId = result.image.id
        navigationController?.pushViewController(detailVC, animated: true)
    }
}

// MARK: - ImageCell

class ImageCell: UICollectionViewCell {
    let imageView = UIImageView()
    let similarityLabel = UILabel()
    
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupViews()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupViews() {
        imageView.contentMode = .scaleAspectFill
        imageView.clipsToBounds = true
        contentView.addSubview(imageView)
        
        similarityLabel.font = .systemFont(ofSize: 12)
        similarityLabel.textColor = .white
        similarityLabel.backgroundColor = UIColor.black.withAlphaComponent(0.6)
        similarityLabel.textAlignment = .center
        contentView.addSubview(similarityLabel)
        
        // 使用 Auto Layout
        imageView.translatesAutoresizingMaskIntoConstraints = false
        similarityLabel.translatesAutoresizingMaskIntoConstraints = false
        
        NSLayoutConstraint.activate([
            imageView.topAnchor.constraint(equalTo: contentView.topAnchor),
            imageView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            imageView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            imageView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
            
            similarityLabel.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
            similarityLabel.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            similarityLabel.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            similarityLabel.heightAnchor.constraint(equalToConstant: 24)
        ])
    }
}
```

### 4. 图片详情页

```swift
import UIKit
import SDWebImage

class ImageDetailViewController: UIViewController {
    
    var imageId: UUID!
    
    private let imageView = UIImageView()
    private let infoLabel = UILabel()
    private let similarButton = UIButton(type: .system)
    
    override func viewDidLoad() {
        super.viewDidLoad()
        setupViews()
        loadImageDetails()
    }
    
    private func setupViews() {
        view.backgroundColor = .systemBackground
        
        imageView.contentMode = .scaleAspectFit
        view.addSubview(imageView)
        
        infoLabel.numberOfLines = 0
        infoLabel.font = .systemFont(ofSize: 14)
        view.addSubview(infoLabel)
        
        similarButton.setTitle("查找相似图片", for: .normal)
        similarButton.addTarget(self, action: #selector(findSimilarTapped), for: .touchUpInside)
        view.addSubview(similarButton)
        
        // Auto Layout
        imageView.translatesAutoresizingMaskIntoConstraints = false
        infoLabel.translatesAutoresizingMaskIntoConstraints = false
        similarButton.translatesAutoresizingMaskIntoConstraints = false
        
        NSLayoutConstraint.activate([
            imageView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 20),
            imageView.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            imageView.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            imageView.heightAnchor.constraint(equalToConstant: 300),
            
            infoLabel.topAnchor.constraint(equalTo: imageView.bottomAnchor, constant: 20),
            infoLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            infoLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            
            similarButton.topAnchor.constraint(equalTo: infoLabel.bottomAnchor, constant: 20),
            similarButton.centerXAnchor.constraint(equalTo: view.centerXAnchor)
        ])
    }
    
    private func loadImageDetails() {
        PhotoSearchAPI.shared.getImageInfo(imageId: imageId) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let imageResponse):
                    self?.updateUI(with: imageResponse)
                case .failure(let error):
                    self?.showAlert(message: "加载失败: \(error.localizedDescription)")
                }
            }
        }
    }
    
    private func updateUI(with image: ImageResponse) {
        // 加载原图
        if let originalUrl = image.originalUrl {
            let fullUrl = "http://localhost:8000" + originalUrl
            imageView.sd_setImage(with: URL(string: fullUrl))
        }
        
        // 显示图片信息
        var infoText = "文件名: \(image.filename)\n"
        infoText += "尺寸: \(image.width ?? 0) x \(image.height ?? 0)\n"
        infoText += "格式: \(image.format ?? "Unknown")\n"
        infoText += "大小: \(formatFileSize(image.fileSize ?? 0))\n"
        infoText += "上传时间: \(formatDate(image.createdAt))"
        infoLabel.text = infoText
    }
    
    @objc private func findSimilarTapped() {
        // 查找相似图片
        let searchVC = SearchViewController()
        searchVC.searchSimilarImages(imageId: imageId)
        navigationController?.pushViewController(searchVC, animated: true)
    }
    
    private func formatFileSize(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
```

## 核心功能实现

### 图片上传队列

```swift
import Foundation

class UploadQueue {
    static let shared = UploadQueue()
    private var queue: [(UIImage, String)] = []
    private var isUploading = false
    
    func add(images: [(UIImage, String)]) {
        queue.append(contentsOf: images)
        processQueue()
    }
    
    private func processQueue() {
        guard !isUploading, !queue.isEmpty else { return }
        isUploading = true
        
        let (image, filename) = queue.removeFirst()
        
        PhotoSearchAPI.shared.uploadImage(image, filename: filename) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success:
                    print("上传成功: \(filename)")
                    NotificationCenter.default.post(name: .imageUploadSuccess, object: nil)
                case .failure(let error):
                    print("上传失败: \(filename), 错误: \(error)")
                }
                
                self?.isUploading = false
                self?.processQueue()
            }
        }
    }
}

extension Notification.Name {
    static let imageUploadSuccess = Notification.Name("imageUploadSuccess")
}
```

### 搜索历史管理

```swift
import Foundation

class SearchHistoryManager {
    static let shared = SearchHistoryManager()
    private let key = "searchHistory"
    private let maxHistoryCount = 50
    
    var history: [String] {
        get {
            UserDefaults.standard.stringArray(forKey: key) ?? []
        }
        set {
            UserDefaults.standard.set(Array(newValue.prefix(maxHistoryCount)), forKey: key)
        }
    }
    
    func add(query: String) {
        var current = history
        current.removeAll { $0 == query }
        current.insert(query, at: 0)
        history = current
    }
    
    func clear() {
        history = []
    }
}
```

## 错误处理

### 常见错误码

| 状态码 | 含义 | 处理方式 |
|--------|------|----------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 检查请求体格式 |
| 404 | 资源不存在 | 图片ID可能无效 |
| 413 | 文件过大 | 压缩图片后重试 |
| 422 | 处理错误 | 图片格式不支持 |
| 500 | 服务器错误 | 稍后重试 |

### 错误处理示例

```swift
enum PhotoSearchError: LocalizedError {
    case invalidImage
    case fileTooLarge
    case networkError
    case serverError(String)
    case imageNotFound
    
    var errorDescription: String? {
        switch self {
        case .invalidImage:
            return "无效的图片文件"
        case .fileTooLarge:
            return "图片文件过大（最大 10MB）"
        case .networkError:
            return "网络连接失败"
        case .serverError(let message):
            return "服务器错误: \(message)"
        case .imageNotFound:
            return "图片不存在"
        }
    }
}
```

## 最佳实践

### 1. 图片压缩

```swift
extension UIImage {
    func compressed(maxSize: CGFloat = 1920, quality: CGFloat = 0.8) -> UIImage? {
        let maxPixel = max(size.width, size.height)
        guard maxPixel > maxSize else { return self }
        
        let scale = maxSize / maxPixel
        let newSize = CGSize(width: size.width * scale, height: size.height * scale)
        
        UIGraphicsBeginImageContextWithOptions(newSize, false, 1.0)
        defer { UIGraphicsEndImageContext() }
        
        draw(in: CGRect(origin: .zero, size: newSize))
        return UIGraphicsGetImageFromCurrentImageContext()
    }
}
```

### 2. 缓存策略

```swift
import SDWebImage

// 配置图片缓存
SDImageCache.shared.config.maxMemoryCost = 100 * 1024 * 1024  // 100MB
SDImageCache.shared.config.maxDiskSize = 500 * 1024 * 1024     // 500MB

// 使用缓存加载图片
imageView.sd_setImage(
    with: url,
    placeholderImage: placeholder,
    options: [.retryFailed, .refreshCached]
)
```

### 3. 网络请求优化

```swift
// 使用 Debounce 避免频繁搜索
class SearchDebouncer {
    private var workItem: DispatchWorkItem?
    
    func debounce(interval: TimeInterval = 0.5, action: @escaping () -> Void) {
        workItem?.cancel()
        workItem = DispatchWorkItem(block: action)
        DispatchQueue.main.asyncAfter(deadline: .now() + interval, execute: workItem!)
    }
}

// 使用示例
let debouncer = SearchDebouncer()

searchTextField.addTarget(self, action: #selector(textDidChange), for: .editingChanged)

@objc func textDidChange() {
    debouncer.debounce { [weak self] in
        self?.performSearch()
    }
}
```

### 4. 离线支持

```swift
import CoreData

// 保存搜索结果到本地
func cacheSearchResults(_ results: [ImageSearchResult], for query: String) {
    // 使用 Core Data 或 UserDefaults 缓存
    let cacheKey = "search_\(query)"
    if let data = try? JSONEncoder().encode(results) {
        UserDefaults.standard.set(data, forKey: cacheKey)
        UserDefaults.standard.set(Date(), forKey: "\(cacheKey)_timestamp")
    }
}

// 读取缓存
func getCachedResults(for query: String) -> [ImageSearchResult]? {
    let cacheKey = "search_\(query)"
    
    // 检查缓存是否过期（24小时）
    if let timestamp = UserDefaults.standard.object(forKey: "\(cacheKey)_timestamp") as? Date,
       Date().timeIntervalSince(timestamp) < 86400,
       let data = UserDefaults.standard.data(forKey: cacheKey),
       let results = try? JSONDecoder().decode([ImageSearchResult].self, from: data) {
        return results
    }
    return nil
}
```

## 完整示例项目

参考项目结构：

```
PhotoSearchApp/
├── App/
│   ├── AppDelegate.swift
│   └── SceneDelegate.swift
├── Network/
│   ├── PhotoSearchAPI.swift
│   └── Models.swift
├── Views/
│   ├── UploadViewController.swift
│   ├── SearchViewController.swift
│   └── ImageDetailViewController.swift
├── Utils/
│   ├── ImageCompressor.swift
│   └── CacheManager.swift
└── Resources/
    └── Assets.xcassets
```

## 调试技巧

1. **查看 API 文档**: 访问 `http://localhost:8000/docs` 查看 Swagger UI
2. **测试网络**: 使用 Safari 开发者工具或 Charles Proxy
3. **日志输出**: 在 Xcode 控制台查看网络请求详情
4. **本地测试**: 使用 iOS Simulator 测试，确保后端服务在同一网络

## 生产环境注意事项

1. **HTTPS**: 生产环境必须使用 HTTPS
2. **API 认证**: 根据需求添加认证机制
3. **错误重试**: 实现指数退避重试策略
4. **图片优化**: 上传前压缩图片，减少流量
5. **分页加载**: 搜索结果多时实现分页
6. **用户反馈**: 提供反馈机制，帮助改进搜索质量

---

**文档版本**: 1.0  
**最后更新**: 2024年
