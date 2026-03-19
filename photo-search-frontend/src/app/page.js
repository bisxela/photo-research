"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  checkHealth,
  getImage,
  resolveBackendAssetUrl,
  searchImages,
  searchSimilarImages,
  uploadImage,
  uploadImages,
} from "@/lib/api";

const sampleQueries = ["节日", "风景", "人物", "建筑", "美食"];
const resultCountOptions = [6, 12, 24, 48];

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [resultLimit, setResultLimit] = useState(12);
  const [status, setStatus] = useState("准备开始");
  const [service, setService] = useState(null);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingUpload, setLoadingUpload] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [recentUploads, setRecentUploads] = useState([]);
  const [uploadErrors, setUploadErrors] = useState([]);
  const uploadPollTimerRef = useRef(null);

  const canSearch = query.trim().length > 0 && !loadingSearch;
  const canUpload = selectedFiles.length > 0 && !loadingUpload;
  const statusTone = getStatusTone(status);
  const statusStyle = {
    idle: "border-stone-200 bg-stone-950 text-stone-100",
    loading: "border-[#d8b088] bg-[#fff3e6] text-[#7d411d]",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-rose-200 bg-rose-50 text-rose-900",
  }[statusTone];
  const statusLabel = {
    idle: "待命",
    loading: "处理中",
    success: "成功",
    error: "异常",
  }[statusTone];

  const summaryText = useMemo(() => {
    if (!results.length) {
      return "还没有结果，先试试上传一张图，或者直接搜“节日”。";
    }

    return `当前共展示 ${results.length} 条结果。点击卡片可以基于这张图继续搜索。`;
  }, [results]);

  useEffect(() => {
    return () => {
      if (uploadPollTimerRef.current) {
        clearTimeout(uploadPollTimerRef.current);
      }
    };
  }, []);

  async function handleHealthCheck() {
    setStatus("检查后端服务中...");
    try {
      const data = await checkHealth();
      setService(data);
      setStatus("后端服务可用，可以继续做前端。 ");
    } catch (error) {
      setStatus(`连接失败：${error.message}`);
    }
  }

  async function handleSearch(nextQuery = query) {
    const safeQuery = nextQuery.trim();
    if (!safeQuery) {
      setStatus("请输入搜索词。");
      return;
    }

    setLoadingSearch(true);
    setStatus(`正在搜索“${safeQuery}”...`);

    try {
      const data = await searchImages(safeQuery, resultLimit);
      setQuery(safeQuery);
      const dedupedResults = dedupeSearchResults(data.results || []);
      setResults(dedupedResults);
      setStatus(`搜索完成，用时 ${data.search_time_ms ?? 0} ms。`);
    } catch (error) {
      setStatus(`搜索失败：${error.message}`);
    } finally {
      setLoadingSearch(false);
    }
  }

  async function handleUpload() {
    if (!selectedFiles.length) {
      setStatus("请先选择图片。");
      return;
    }

    setLoadingUpload(true);
    setUploadErrors([]);
    setStatus(
      selectedFiles.length === 1
        ? `正在上传 ${selectedFiles[0].name} ...`
        : `正在批量上传 ${selectedFiles.length} 张图片...`
    );

    try {
      if (selectedFiles.length === 1) {
        const data = await uploadImage(selectedFiles[0]);
        setRecentUploads([data]);
        setStatus("上传成功，正在后台编码图片向量...");
        startUploadStatusPolling([data.id]);
      } else {
        const data = await uploadImages(selectedFiles);
        setRecentUploads(data.images || []);
        setUploadErrors(data.errors || []);

        if (data.images?.length) {
          setStatus(
            `批量上传完成：成功 ${data.success_count} 张，失败 ${data.failed_count} 张。正在后台编码成功上传的图片...`
          );
          startUploadStatusPolling((data.images || []).map((item) => item.id));
        } else {
          setStatus(`批量上传失败：${data.failed_count} 张失败，没有图片成功上传。`);
        }
      }

      setSelectedFiles([]);
    } catch (error) {
      setStatus(`上传失败：${error.message}`);
    } finally {
      setLoadingUpload(false);
    }
  }

  async function handleSimilarSearch(imageId) {
    setLoadingSearch(true);
    setStatus("正在查找相似图片...");

    try {
      const data = await searchSimilarImages(imageId, resultLimit);
      const dedupedResults = dedupeSearchResults(data.results || []);
      setResults(dedupedResults);
      setStatus(`相似图搜索完成，用时 ${data.search_time_ms ?? 0} ms。`);
    } catch (error) {
      setStatus(`相似图搜索失败：${error.message}`);
    } finally {
      setLoadingSearch(false);
    }
  }

  function startUploadStatusPolling(imageIds) {
    if (uploadPollTimerRef.current) {
      clearTimeout(uploadPollTimerRef.current);
    }

    let attempts = 0;
    const maxAttempts = 30;
    const poll = async () => {
      attempts += 1;

      try {
        const images = await Promise.all(imageIds.map((imageId) => getImage(imageId)));
        setRecentUploads(images);

        const readyCount = images.filter((image) => image.embedding_ready).length;
        if (readyCount === images.length) {
          setStatus(
            images.length === 1
              ? "上传成功，图片已完成编码，现在可以直接做相似图搜索。"
              : `批量上传的 ${images.length} 张图片都已完成编码，可以开始检索了。`
          );
          uploadPollTimerRef.current = null;
          return;
        }

        if (attempts >= maxAttempts) {
          setStatus(
            `上传成功，目前已有 ${readyCount}/${images.length} 张图片完成编码。你可以稍后再试。`
          );
          uploadPollTimerRef.current = null;
          return;
        }

        setStatus(
          `上传成功，正在后台编码图片向量...（已完成 ${readyCount}/${images.length}，第 ${attempts} 次检查）`
        );
        uploadPollTimerRef.current = setTimeout(poll, 2000);
      } catch (error) {
        setStatus(`上传成功，但查询编码状态失败：${error.message}`);
        uploadPollTimerRef.current = null;
      }
    };

    poll();
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#fff8ef,_#f5efe5_50%,_#eadfce)] px-4 py-6 text-stone-900 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <section className="overflow-hidden rounded-[28px] border border-stone-200/70 bg-white/85 p-5 shadow-[0_24px_80px_rgba(84,57,24,0.08)] backdrop-blur sm:p-8">
          <div className="flex flex-col gap-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-stone-500">
                  Photo Search
                </p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-5xl">
                  图片语义检索工作台
                </h1>
              </div>
              <button
                onClick={handleHealthCheck}
                className="rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-900 hover:text-stone-950"
              >
                检查后端
              </button>
            </div>

            <p className="max-w-3xl text-sm leading-7 text-stone-600 sm:text-base">
              上传图片、执行文本检索、查看相似结果都集中在同一页完成。
              当前页面已经接入后端搜索、上传、缩略图与相似图能力，适合直接作为本地联调与功能验证入口。
            </p>

            <div className="grid gap-3 sm:grid-cols-3">
              <InfoCard title="检索方式" value="文本搜图 / 以图搜图" />
              <InfoCard title="处理流程" value="上传 -> 编码 -> 检索" />
              <InfoCard title="运行模式" value="前端 + FastAPI 后端" />
            </div>

            <div className={`rounded-[24px] border px-4 py-4 shadow-sm ${statusStyle}`}>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] opacity-75">
                  {statusLabel}
                </p>
                <div className="h-2.5 w-2.5 rounded-full bg-current opacity-70" />
              </div>
              <p className="mt-2 text-sm leading-6">{status}</p>
            </div>

            {service ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <InfoCard title="服务状态" value={service.status} subtle />
                <InfoCard title="数据库" value={service.services?.database ?? "unknown"} subtle />
                <InfoCard title="模型" value={service.services?.model ?? "unknown"} subtle />
              </div>
            ) : null}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.05fr_1.45fr]">
          <div className="flex flex-col gap-6">
            <Panel
              title="上传图片区"
              hint="支持单张上传与批量上传，编码完成后即可参与检索。"
              tone="warm"
            >
              <label className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-[#d8b088] bg-[linear-gradient(180deg,_#fff7ee,_#fff1e4)] px-4 py-6 text-center text-sm text-stone-500 transition hover:border-[#c58558] hover:bg-[linear-gradient(180deg,_#fff4ea,_#ffe9d7)]">
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  className="hidden"
                  onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
                />
                <span className="text-base font-medium text-stone-700">选择一张或多张图片</span>
                <span className="mt-2">支持 jpg、png、gif、bmp、webp，后端限制 10MB。</span>
              </label>

              <div className="rounded-2xl border border-[#eadbc8] bg-white px-4 py-3 text-sm text-stone-600">
                {selectedFiles.length
                  ? `当前已选择 ${selectedFiles.length} 个文件：${selectedFiles
                      .slice(0, 3)
                      .map((file) => file.name)
                      .join("、")}${selectedFiles.length > 3 ? "..." : ""}`
                  : "还没有选中文件。"}
              </div>

              <button
                onClick={handleUpload}
                disabled={!canUpload}
                className="w-full rounded-full bg-[#9e4f20] px-5 py-3 text-sm font-semibold text-white transition enabled:hover:bg-[#84411a] disabled:cursor-not-allowed disabled:bg-stone-300"
              >
                {loadingUpload
                  ? "上传中..."
                  : selectedFiles.length > 1
                    ? "批量上传到后端"
                    : "上传到后端"}
              </button>

              {uploadErrors.length ? (
                <div className="rounded-3xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
                  <p className="text-sm font-medium text-amber-900">批量上传中的失败项</p>
                  <div className="mt-2 space-y-1 text-xs text-amber-800">
                    {uploadErrors.map((error) => (
                      <p key={error}>{error}</p>
                    ))}
                  </div>
                </div>
              ) : null}

              {recentUploads.length ? (
                <div className="rounded-3xl border border-[#eadbc8] bg-[#fffaf5] p-4 shadow-sm">
                  <p className="text-sm font-medium text-stone-800">
                    最近一次上传
                    {recentUploads.length > 1 ? `（共 ${recentUploads.length} 张）` : ""}
                  </p>
                  <div className="mt-3 space-y-3">
                    {recentUploads.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-2xl border border-[#eadbc8] bg-white px-4 py-3"
                      >
                        <p className="text-sm text-stone-700">{item.filename}</p>
                        <p className="mt-1 text-xs text-stone-500">ID: {item.id}</p>
                        <p className="mt-1 text-xs text-stone-500">
                          编码状态：{item.embedding_ready ? "已完成" : "进行中"}
                        </p>
                        <button
                          onClick={() => handleSimilarSearch(item.id)}
                          disabled={!item.embedding_ready}
                          className="mt-3 rounded-full border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 transition hover:border-stone-900 hover:text-stone-950 disabled:cursor-not-allowed disabled:border-stone-200 disabled:text-stone-400"
                        >
                          {item.embedding_ready ? "基于它查相似图" : "编码中，暂不可搜索"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </Panel>

            <Panel title="当前能力" hint="这一页已经覆盖最常用的本地联调场景。" tone="neutral">
              <ol className="space-y-3 text-sm leading-7 text-stone-600">
                <li>1. 文本搜索：输入关键词，直接返回语义检索结果。</li>
                <li>2. 图片上传：支持上传后自动轮询编码状态。</li>
                <li>3. 相似图搜索：基于现有图片继续做向量检索。</li>
                <li>4. 原图查看：结果卡片可直接打开原始图片。</li>
                <li>5. 服务检查：页面内可以快速查看后端、数据库和模型状态。</li>
              </ol>
            </Panel>
          </div>

          <div className="flex flex-col gap-6">
            <Panel
              title="文本搜索区"
              hint="输入关键词后，系统会返回最相关的图片结果。"
              tone="accent"
            >
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="输入关键词，例如 节日、风景、美食"
                  className="min-h-12 flex-1 rounded-full border border-[#d8b088] bg-white px-4 text-sm outline-none transition focus:border-[#9e4f20]"
                />
                <button
                  onClick={() => handleSearch()}
                  disabled={!canSearch}
                  className="min-h-12 rounded-full bg-[#b75d2a] px-5 text-sm font-semibold text-white transition enabled:hover:bg-[#9f4f21] disabled:cursor-not-allowed disabled:bg-stone-300"
                >
                  {loadingSearch ? "搜索中..." : "开始搜索"}
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                {sampleQueries.map((item) => (
                  <button
                    key={item}
                    onClick={() => handleSearch(item)}
                    className="rounded-full border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-600 transition hover:border-stone-900 hover:text-stone-950"
                  >
                    {item}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-stone-500">
                  返回张数
                </span>
                {resultCountOptions.map((count) => (
                  <button
                    key={count}
                    onClick={() => setResultLimit(count)}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                      resultLimit === count
                        ? "border border-[#9e4f20] bg-[#fff1e7] text-[#8f4317]"
                        : "border border-stone-300 text-stone-600 hover:border-stone-900 hover:text-stone-950"
                    }`}
                  >
                    {count} 张
                  </button>
                ))}
              </div>

              <p className="text-sm leading-7 text-stone-600">{summaryText}</p>
            </Panel>

            <section className="rounded-[24px] border border-stone-200/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.94),_rgba(249,245,240,0.92))] p-3 shadow-[0_24px_80px_rgba(84,57,24,0.08)] sm:rounded-[28px] sm:p-5">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">
                    Results
                  </p>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight text-stone-950">
                    检索结果区
                  </h2>
                </div>
                <p className="text-sm text-stone-500">
                  {results.length ? `共 ${results.length} 张` : "等待结果"}
                </p>
              </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
              {results.map((item) => {
                const imageUrl = resolveBackendAssetUrl(item.image.thumbnail_url);

                return (
                  <article
                    key={item.image.id}
                    className="overflow-hidden rounded-[22px] border border-stone-200 bg-white shadow-[0_18px_40px_rgba(84,57,24,0.08)]"
                  >
                    <div className="aspect-square bg-stone-100">
                      {imageUrl ? (
                        <Image
                          src={imageUrl}
                          alt={item.image.filename}
                          width={400}
                          height={400}
                          unoptimized
                          className="h-full w-full object-cover"
                        />
                      ) : null}
                    </div>
                    <div className="space-y-3 p-3 sm:p-5">
                      <div>
                        <p className="line-clamp-2 text-sm font-semibold leading-5 text-stone-900 sm:text-base sm:leading-6">
                          {item.image.filename}
                        </p>
                        <p className="mt-1 text-xs text-stone-500 sm:text-sm">
                          相似度 {Number(item.similarity_score).toFixed(3)}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-500 sm:text-sm">
                        <span>{item.image.width ?? "?"} x {item.image.height ?? "?"}</span>
                        <span>{item.image.format ?? "unknown"}</span>
                      </div>

                      <div className="flex flex-col gap-2">
                        <button
                          onClick={() => handleSimilarSearch(item.image.id)}
                          className="min-h-10 rounded-full border border-stone-300 px-3 py-2.5 text-xs font-medium text-stone-700 transition hover:border-stone-900 hover:text-stone-950 sm:min-h-11 sm:px-4 sm:py-3 sm:text-sm"
                        >
                          查相似图
                        </button>
                        {item.image.original_url ? (
                          <a
                            href={resolveBackendAssetUrl(item.image.original_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="min-h-10 rounded-full border border-[#b75d2a] bg-[#fff1e7] px-3 py-2.5 text-center text-xs font-semibold text-[#8f4317] transition hover:bg-[#ffe4d2] hover:text-[#723311] sm:min-h-11 sm:px-4 sm:py-3 sm:text-sm"
                          >
                            查看原图 ↗
                          </a>
                        ) : null}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

function dedupeSearchResults(items) {
  const seen = new Set();

  return items.filter((item) => {
    const key = [
      item?.image?.filename ?? "",
      item?.image?.width ?? "",
      item?.image?.height ?? "",
      item?.image?.file_size ?? "",
      item?.image?.format ?? "",
    ].join("|");

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
}

function getStatusTone(status) {
  if (status.includes("失败") || status.includes("异常") || status.includes("连接失败")) {
    return "error";
  }

  if (
    status.includes("成功") ||
    status.includes("完成") ||
    status.includes("可用") ||
    status.includes("已完成")
  ) {
    return "success";
  }

  if (
    status.includes("正在") ||
    status.includes("检查") ||
    status.includes("上传中") ||
    status.includes("搜索中") ||
    status.includes("编码")
  ) {
    return "loading";
  }

  return "idle";
}

function Panel({ title, hint, children, tone = "neutral" }) {
  const toneClass = {
    warm: "border-[#eadbc8] bg-[linear-gradient(180deg,_rgba(255,248,239,0.96),_rgba(255,243,230,0.9))]",
    accent:
      "border-[#eadbc8] bg-[linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(251,241,232,0.94))]",
    neutral: "border-stone-200/70 bg-white/90",
  }[tone];

  return (
    <section className={`rounded-[28px] border p-5 shadow-[0_24px_80px_rgba(84,57,24,0.08)] sm:p-6 ${toneClass}`}>
      <div className="mb-4">
        <h2 className="text-xl font-semibold tracking-tight text-stone-950">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-stone-500">{hint}</p>
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

function InfoCard({ title, value, subtle = false }) {
  return (
    <div
      className={`rounded-2xl border px-4 py-3 ${
        subtle
          ? "border-stone-200 bg-stone-50"
          : "border-stone-200/70 bg-[#f8f2ea]"
      }`}
    >
      <p className="text-xs uppercase tracking-[0.22em] text-stone-500">{title}</p>
      <p className="mt-2 text-sm font-medium text-stone-900">{value}</p>
    </div>
  );
}
