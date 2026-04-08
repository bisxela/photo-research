"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  checkHealth,
  getCurrentUser,
  getImage,
  getImageOcr,
  listImages,
  login,
  register,
  resolveBackendAssetUrl,
  saveImageOcr,
  searchImages,
  searchSimilarImages,
  uploadImage,
  uploadImages,
} from "@/lib/api";

const sampleQueries = ["节日", "风景", "人物", "建筑", "美食", "抽象"];
const ocrExamples = ["咖啡店菜单", "快递单号", "路牌文字", "发票抬头", "海报标题"];
const resultCountOptions = [12, 24, 48, 96];
const TOKEN_STORAGE_KEY = "photo-search-access-token";

export default function Home() {
  const [sessionToken, setSessionToken] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ username: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [searchMode, setSearchMode] = useState("semantic");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [galleryImages, setGalleryImages] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [resultLimit, setResultLimit] = useState(24);
  const [status, setStatus] = useState("准备就绪");
  const [service, setService] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingUpload, setLoadingUpload] = useState(false);
  const [loadingGallery, setLoadingGallery] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [recentUploads, setRecentUploads] = useState([]);
  const [uploadErrors, setUploadErrors] = useState([]);
  const uploadPollTimerRef = useRef(null);
  const ocrCacheRef = useRef(new Map());
  const autoOcrProcessedRef = useRef(new Set());
  const autoOcrRunningRef = useRef(false);
  const [ocrState, setOcrState] = useState({
    imageId: "",
    loading: false,
    progress: 0,
    stage: "",
    text: "",
    error: "",
  });
  const [autoOcrSummary, setAutoOcrSummary] = useState({
    total: 0,
    completed: 0,
    running: false,
  });

  // --- 样式逻辑映射 ---
  const statusTone = getStatusTone(status);
  const statusStyle = {
    idle: "bg-slate-100 text-slate-600 border-slate-200",
    loading: "bg-blue-50 text-blue-700 border-blue-100 animate-pulse",
    success: "bg-emerald-50 text-emerald-700 border-emerald-100",
    error: "bg-rose-50 text-rose-700 border-rose-100",
  }[statusTone];

  // --- 以下逻辑保持不变 ---
  const canSearch = query.trim().length > 0 && !loadingSearch && Boolean(sessionToken);
  const canUpload = selectedFiles.length > 0 && !loadingUpload && Boolean(sessionToken);
  const isGalleryMode = results.length === 0;
  const displayItems = results.length > 0 ? results : galleryImages.map((image) => ({
    image,
    similarity_score: null,
  }));
  const recentGalleryItems = useMemo(
    () =>
      galleryImages.slice(0, 4).map((image) => ({
        image,
        similarity_score: null,
      })),
    [galleryImages]
  );
  const galleryGroups = useMemo(() => {
    const groups = [];
    const grouped = new Map();

    for (const image of galleryImages) {
      const label = formatMonthLabel(image.created_at);
      if (!grouped.has(label)) {
        grouped.set(label, []);
        groups.push({ label, items: grouped.get(label) });
      }
      grouped.get(label).push({
        image,
        similarity_score: null,
      });
    }

    return groups;
  }, [galleryImages]);
  const selectedItemIndex = useMemo(() => {
    if (!selectedItem) return -1;
    return displayItems.findIndex((item) => item.image.id === selectedItem.image.id);
  }, [displayItems, selectedItem]);
  const hasPrevItem = selectedItemIndex > 0;
  const hasNextItem = selectedItemIndex >= 0 && selectedItemIndex < displayItems.length - 1;
  const selectedOcrCache = selectedItem ? ocrCacheRef.current.get(selectedItem.image.id) || "" : "";
  const selectedOcrState = selectedItem && ocrState.imageId === selectedItem.image.id ? ocrState : null;
  const hasSelectedOcrResult = selectedItem && ocrState.imageId === selectedItem.image.id && !ocrState.error;

  function cleanupPollTimer() { if (uploadPollTimerRef.current) clearTimeout(uploadPollTimerRef.current); }
  function clearSession() {
    clearStoredToken();
    setSessionToken("");
    setCurrentUser(null);
    setResults([]);
    setGalleryImages([]);
    setRecentUploads([]);
    setSelectedFiles([]);
    setUploadErrors([]);
    autoOcrProcessedRef.current = new Set();
    autoOcrRunningRef.current = false;
    setAutoOcrSummary({ total: 0, completed: 0, running: false });
  }

  const loadGallery = useCallback(async (token = sessionToken) => {
    if (!token) return;
    setLoadingGallery(true);
    try {
      const images = await listImages(token);
      setGalleryImages(images || []);
    } catch (error) {
      setStatus(`加载图库失败: ${error.message}`);
    } finally {
      setLoadingGallery(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    const storedToken = readStoredToken();
    if (!storedToken) return cleanupPollTimer;
    setSessionToken(storedToken);
    void (async () => {
      try {
        const user = await getCurrentUser(storedToken);
        setCurrentUser(user);
        setStatus(`欢迎回来，${user.username}`);
        await loadGallery(storedToken);
      } catch (error) {
        clearStoredToken();
        setSessionToken("");
        setCurrentUser(null);
      }
    })();
    return cleanupPollTimer;
  }, [loadGallery]);

  useEffect(() => {
    if (!selectedItem) return undefined;

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setSelectedItem(null);
        return;
      }

      if (event.key === "ArrowLeft" && hasPrevItem) {
        setSelectedItem(displayItems[selectedItemIndex - 1]);
        return;
      }

      if (event.key === "ArrowRight" && hasNextItem) {
        setSelectedItem(displayItems[selectedItemIndex + 1]);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [displayItems, hasNextItem, hasPrevItem, selectedItem, selectedItemIndex]);

  useEffect(() => {
    if (!selectedItem || !sessionToken) return undefined;

    const imageId = selectedItem.image.id;
    if (ocrCacheRef.current.has(imageId)) {
      const cachedText = ocrCacheRef.current.get(imageId) || "";
      setOcrState({
        imageId,
        loading: false,
        progress: 1,
        stage: "done",
        text: cachedText,
        error: "",
      });
      return undefined;
    }

    let cancelled = false;

    void (async () => {
      try {
        const data = await getImageOcr(sessionToken, imageId);
        if (cancelled) return;
        const text = (data?.text || "").trim();
        ocrCacheRef.current.set(imageId, text);
        setOcrState({
          imageId,
          loading: false,
          progress: text ? 1 : 0,
          stage: text ? "done" : "",
          text,
          error: "",
        });
      } catch (error) {
        if (cancelled) return;
        setOcrState({
          imageId,
          loading: false,
          progress: 0,
          stage: "",
          text: "",
          error: "",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedItem, sessionToken]);

  async function handleHealthCheck() {
    setStatus("检查服务...");
    try {
      const data = await checkHealth();
      setService(data);
      setStatus("服务连接正常");
    } catch (error) {
      setStatus(`连接失败: ${error.message}`);
    }
  }

  async function handleAuthSubmit() {
    const { username, password } = authForm;
    if (!username || !password) return setStatus("请填写完整信息");
    setLoadingAuth(true);
    try {
      const data = authMode === "register" 
        ? await register(username, password) 
        : await login(username, password);
      persistSession(data.access_token);
      setSessionToken(data.access_token);
      setCurrentUser(data.user);
      setResults([]);
      await loadGallery(data.access_token);
      setStatus(`${authMode === "login" ? "登录" : "注册"}成功`);
    } catch (error) {
      setStatus(`错误: ${error.message}`);
    } finally {
      setLoadingAuth(false);
    }
  }

  function handleLogout() {
    clearSession();
    setAuthForm({ username: "", password: "" });
    setShowPassword(false);
    setSelectedItem(null);
    ocrCacheRef.current = new Map();
    setOcrState({
      imageId: "",
      loading: false,
      progress: 0,
      stage: "",
      text: "",
      error: "",
    });
    setStatus("已退出登录");
  }

  async function handleSearch(nextQuery = query) {
    const q = nextQuery.trim();
    if (!q || !sessionToken) return;
    setLoadingSearch(true);
    setStatus(
      searchMode === "ocr"
        ? `正在以 OCR 场景搜索 "${q}"...`
        : `正在搜索 "${q}"...`
    );
    try {
      const data = await searchImages(sessionToken, q, resultLimit, searchMode);
      setQuery(q);
      setResults(dedupeSearchResults(data.results || []));
      if (searchMode === "ocr") {
        setStatus(
          `OCR 搜索返回 ${data.results?.length || 0} 张结果，已优先参考已保存的图中文字。`
        );
      } else {
        setStatus(`找到 ${data.results?.length || 0} 张相关图片`);
      }
    } catch (error) {
      setStatus(`搜索出错: ${error.message}`);
    } finally {
      setLoadingSearch(false);
    }
  }

  async function handleUpload() {
    if (!selectedFiles.length || !sessionToken) return;
    setLoadingUpload(true);
    setStatus("上传中...");
    setUploadErrors([]);
    try {
      if (selectedFiles.length === 1) {
        const data = await uploadImage(sessionToken, selectedFiles[0]);
        setRecentUploads([data]);
        void processRecentUploadsOcr([data]);
        startUploadStatusPolling([data.id]);
      } else {
        const data = await uploadImages(sessionToken, selectedFiles);
        setRecentUploads(data.images || []);
        void processRecentUploadsOcr(data.images || []);
        if (data.images?.length) startUploadStatusPolling(data.images.map(i => i.id));
      }
      setSelectedFiles([]);
      await loadGallery(sessionToken);
    } catch (error) {
      setStatus(`上传失败: ${error.message}`);
    } finally {
      setLoadingUpload(false);
    }
  }

  async function handleSimilarSearch(imageId) {
    if (!sessionToken) return;
    setLoadingSearch(true);
    setStatus("正在寻找相似视觉结果...");
    try {
      const data = await searchSimilarImages(sessionToken, imageId, resultLimit);
      setResults(dedupeSearchResults(data.results || []));
      setSelectedItem(null);
      setStatus("相似图搜索完成");
    } catch (error) {
      setStatus(`搜索失败: ${error.message}`);
    } finally {
      setLoadingSearch(false);
    }
  }

  async function handleRunOcr(item = selectedItem, options = {}) {
    if (!item?.image?.id) return;
    const { silent = false } = options;

    const imageId = item.image.id;
    const reflectsSelectedItem = selectedItem?.image?.id === imageId;
    const cachedText = ocrCacheRef.current.get(imageId);
    if (cachedText) {
      if (!silent || reflectsSelectedItem) {
        setOcrState({
          imageId,
          loading: false,
          progress: 1,
          stage: "done",
          text: cachedText,
          error: "",
        });
      }
      if (!silent) {
        setStatus("已显示缓存的 OCR 结果");
      }
      return { status: "cached", text: cachedText };
    }

    try {
      const existingOcr = await getImageOcr(sessionToken, imageId);
      const savedText = (existingOcr?.text || "").trim();
      if (savedText) {
        ocrCacheRef.current.set(imageId, savedText);
        if (!silent || reflectsSelectedItem) {
          setOcrState({
            imageId,
            loading: false,
            progress: 1,
            stage: "done",
            text: savedText,
            error: "",
          });
        }
        if (!silent) {
          setStatus("已显示已保存的 OCR 结果");
        }
        return { status: "stored", text: savedText };
      }
    } catch {
      // 忽略读取失败，继续尝试本地 OCR
    }

    const imageUrl = resolveBackendAssetUrl(item.image.original_url || item.image.thumbnail_url);
    if (!imageUrl) {
      if (!silent || reflectsSelectedItem) {
        setOcrState({
          imageId,
          loading: false,
          progress: 0,
          stage: "",
          text: "",
          error: "当前图片没有可识别的地址",
        });
      }
      if (!silent) {
        setStatus("OCR 无法启动，图片地址不可用");
      }
      return { status: "error", message: "当前图片没有可识别的地址" };
    }

    if (!silent || reflectsSelectedItem) {
      setOcrState({
        imageId,
        loading: true,
        progress: 0,
        stage: "准备 OCR 引擎",
        text: "",
        error: "",
      });
    }
    if (!silent) {
      setStatus("正在识别图中文字...");
    }

    try {
      const { recognize } = await import("tesseract.js");
      const result = await recognize(imageUrl, "chi_sim+eng", {
        logger: (message) => {
          if (!silent || reflectsSelectedItem) {
            setOcrState((current) => {
              if (current.imageId !== imageId) return current;
              return {
                ...current,
                stage: message.status || current.stage,
                progress:
                  typeof message.progress === "number" ? message.progress : current.progress,
              };
            });
          }
        },
      });

      const text = (result?.data?.text || "").trim();
      await saveImageOcr(sessionToken, imageId, text, "chi_sim+eng", "client_tesseract");
      ocrCacheRef.current.set(imageId, text);
      if (!silent || reflectsSelectedItem) {
        setOcrState({
          imageId,
          loading: false,
          progress: 1,
          stage: "done",
          text,
          error: "",
        });
      }
      if (!silent) {
        setStatus(text ? "OCR 识别完成" : "OCR 完成，但未识别到明显文字");
      }
      return { status: text ? "success" : "empty", text };
    } catch (error) {
      if (!silent || reflectsSelectedItem) {
        setOcrState({
          imageId,
          loading: false,
          progress: 0,
          stage: "",
          text: "",
          error: error.message || "OCR 执行失败",
        });
      }
      if (!silent) {
        setStatus(`OCR 失败: ${error.message}`);
      }
      return { status: "error", message: error.message || "OCR 执行失败" };
    }
  }

  async function waitForServerOcr(imageId, attempts = 4, delayMs = 1500) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const data = await getImageOcr(sessionToken, imageId);
        const text = (data?.text || "").trim();
        if (text) {
          ocrCacheRef.current.set(imageId, text);
          return { status: "ready", text, source: data?.source || "server" };
        }
        if (data?.status === "empty") {
          return { status: "empty", text: "", source: data?.source || "server" };
        }
      } catch {
        // 忽略单次查询失败，继续等待
      }

      if (attempt < attempts - 1) {
        await sleep(delayMs);
      }
    }

    return { status: "pending" };
  }

  async function processRecentUploadsOcr(images) {
    const candidates = (images || []).filter((image) => image?.id && !autoOcrProcessedRef.current.has(image.id));
    if (!candidates.length || autoOcrRunningRef.current) return;

    autoOcrRunningRef.current = true;
    setAutoOcrSummary({
      total: candidates.length,
      completed: 0,
      running: true,
    });

    const errors = [];

    for (let index = 0; index < candidates.length; index += 1) {
      const image = candidates[index];
      autoOcrProcessedRef.current.add(image.id);
      setStatus(`正在检查上传图片的 OCR 结果 (${index + 1}/${candidates.length})...`);

      const serverResult = await waitForServerOcr(image.id);
      if (serverResult.status === "pending") {
        setStatus(`后端 OCR 尚未完成，正在本地兜底识别 (${index + 1}/${candidates.length})...`);
        const result = await handleRunOcr({ image }, { silent: true });
        if (result?.status === "error") {
          errors.push(`${image.filename}: ${result.message}`);
        }
      } else if (serverResult.status === "ready") {
        setStatus(`后端 OCR 已完成，已同步 ${image.filename}`);
      }

      setAutoOcrSummary({
        total: candidates.length,
        completed: index + 1,
        running: index + 1 < candidates.length,
      });
    }

    autoOcrRunningRef.current = false;
    setUploadErrors(errors);
    await loadGallery(sessionToken);
    setStatus(
      errors.length
        ? `上传完成，OCR 已处理 ${candidates.length} 张，其中 ${errors.length} 张失败`
        : `上传与 OCR 处理完成，共 ${candidates.length} 张`
    );
  }

  function startUploadStatusPolling(imageIds) {
    if (uploadPollTimerRef.current) clearTimeout(uploadPollTimerRef.current);
    let attempts = 0;
    const poll = async () => {
      attempts++;
      try {
        const images = await Promise.all(imageIds.map(id => getImage(sessionToken, id)));
        setRecentUploads(images);
        const ready = images.every(i => i.embedding_ready);
        if (ready || attempts > 20) {
          setStatus(ready ? "编码完成，可以检索了" : "部分图片仍在处理中");
          void loadGallery(sessionToken);
          return;
        }
        setStatus(`图片处理中 (${images.filter(i => i.embedding_ready).length}/${images.length})`);
        uploadPollTimerRef.current = setTimeout(poll, 2000);
      } catch {
        setStatus("状态同步异常");
      }
    };
    poll();
  }

  function openDetail(item) {
    setSelectedItem(item);
  }

  function closeDetail() {
    setSelectedItem(null);
  }

  function goToPrevDetail() {
    if (!hasPrevItem) return;
    setSelectedItem(displayItems[selectedItemIndex - 1]);
  }

  function goToNextDetail() {
    if (!hasNextItem) return;
    setSelectedItem(displayItems[selectedItemIndex + 1]);
  }

  return (
    <main className="min-h-screen pb-20">
      {/* 顶部导航栏 */}
      <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">P</span>
            </div>
            <h1 className="text-lg font-bold tracking-tight text-slate-900 hidden sm:block">Photo Search</h1>
          </div>
          
          <div className="flex items-center gap-4">
            <div className={`px-3 py-1 rounded-full border text-xs font-medium ${statusStyle}`}>
              {status}
            </div>
            {currentUser && (
              <button onClick={handleLogout} className="text-sm font-medium text-slate-500 hover:text-rose-600">
                退出
              </button>
            )}
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6">
        {/* 未登录展示：登录卡片 */}
        {!currentUser && (
          <div className="mx-auto max-w-md py-12">
            <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/50">
              <h2 className="text-2xl font-bold text-slate-900">{authMode === 'login' ? '欢迎回来' : '创建账号'}</h2>
              <p className="mt-2 text-sm text-slate-500">登录以开始您的 AI 语义搜索体验</p>
              <div className="mt-6 space-y-4">
                <div className="flex p-1 bg-slate-100 rounded-xl">
                  <button onClick={() => setAuthMode('login')} className={`flex-1 py-2 text-sm font-medium rounded-lg ${authMode === 'login' ? 'bg-white shadow-sm' : ''}`}>登录</button>
                  <button onClick={() => setAuthMode('register')} className={`flex-1 py-2 text-sm font-medium rounded-lg ${authMode === 'register' ? 'bg-white shadow-sm' : ''}`}>注册</button>
                </div>
                <input 
                  className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none" 
                  placeholder="用户名" 
                  value={authForm.username}
                  onChange={e => setAuthForm({...authForm, username: e.target.value})}
                />
                <div className="flex items-center rounded-xl border border-slate-200 bg-white pr-2 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-200">
                  <input 
                    type={showPassword ? "text" : "password"}
                    className="w-full rounded-xl border-0 bg-transparent px-4 py-3 text-sm outline-none" 
                    placeholder="密码" 
                    value={authForm.password}
                    onChange={e => setAuthForm({...authForm, password: e.target.value})}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    title={showPassword ? "隐藏密码" : "显示密码"}
                    className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10.6 10.7a2 2 0 002.7 2.7" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.9 5.1A10.9 10.9 0 0112 4.9c5 0 8.8 3.2 10 7.1a11.8 11.8 0 01-4.1 5.6" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6.2 6.3C4.1 7.8 2.6 9.8 2 12c1.2 3.9 5 7.1 10 7.1 1.5 0 2.9-.3 4.2-.8" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
                <button 
                  onClick={handleAuthSubmit}
                  disabled={loadingAuth}
                  className="w-full rounded-xl bg-indigo-600 py-3 font-semibold text-white hover:bg-indigo-700 disabled:bg-slate-300"
                >
                  {loadingAuth ? "处理中..." : (authMode === 'login' ? '进入系统' : '立即注册')}
                </button>
              </div>
            </div>
          </div>
        )}

        {currentUser && (
          <div className="space-y-10">
            {/* 核心搜索区 */}
            <section className="mx-auto max-w-3xl text-center">
              <div className="mb-4 flex flex-wrap justify-center gap-2">
                <button
                  onClick={() => setSearchMode("semantic")}
                  className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                    searchMode === "semantic"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  语义搜图
                </button>
                <button
                  onClick={() => setSearchMode("ocr")}
                  className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
                    searchMode === "ocr"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  图中文字入口
                </button>
              </div>

              <div className="relative group">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder={
                    searchMode === "ocr"
                      ? "试试搜“咖啡店菜单”“快递单号”“海报标题”..."
                      : "试试搜“夕阳下的海滩”或“穿西装的人”..."
                  }
                  className="w-full rounded-full border-2 border-slate-200 bg-white px-8 py-5 text-lg shadow-lg shadow-slate-200/40 outline-none focus:border-indigo-500 group-hover:border-slate-300"
                />
                <button
                  onClick={() => handleSearch()}
                  disabled={!canSearch}
                  className="absolute right-3 top-3 h-10 rounded-full bg-indigo-600 px-6 text-sm font-bold text-white hover:bg-indigo-700 disabled:bg-slate-200"
                >
                  {loadingSearch ? "..." : "搜索"}
                </button>
              </div>
              
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {(searchMode === "ocr" ? ocrExamples : sampleQueries).map((item) => (
                  <button
                    key={item}
                    onClick={() => handleSearch(item)}
                    className="rounded-full bg-slate-100 px-4 py-1.5 text-xs font-medium text-slate-600 hover:bg-indigo-50 hover:text-indigo-600"
                  >
                    {item}
                  </button>
                ))}
              </div>

              <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 px-5 py-4 text-left shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                  {searchMode === "ocr" ? "OCR 入口说明" : "当前搜索说明"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {searchMode === "ocr"
                    ? "OCR 模式会优先利用已经保存到图库里的图中文字，适合查找菜单、路牌、发票、海报、快递单等内容。先在图片详情里执行一次文字识别，后续搜索命中会更准确。"
                    : "语义搜图适合描述画面内容，例如人物、风景、建筑、食物、场景氛围等。"}
                </p>
              </div>
            </section>

            {/* 功能分栏 */}
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
              {/* 左侧控制栏 */}
              <aside className="space-y-6 lg:col-span-1">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-900 mb-4 uppercase tracking-wider">上传新图片</h3>
                  <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-6 transition hover:border-indigo-400 hover:bg-indigo-50 cursor-pointer">
                    <input type="file" multiple accept="image/*" className="hidden" onChange={(e) => setSelectedFiles(Array.from(e.target.files || []))} />
                    <span className="text-xs font-semibold text-slate-500">点击或拖拽上传</span>
                  </label>
                  {selectedFiles.length > 0 && (
                    <div className="mt-4">
                      <p className="text-xs text-slate-500 mb-2">已选择 {selectedFiles.length} 个文件</p>
                      <button onClick={handleUpload} disabled={loadingUpload} className="w-full rounded-lg bg-indigo-50 py-2 text-xs font-bold text-indigo-600 hover:bg-indigo-100">
                        {loadingUpload ? "上传中..." : "开始上传"}
                      </button>
                    </div>
                  )}
                  {autoOcrSummary.running && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                      <div className="flex items-center justify-between gap-3 text-[11px] font-medium text-slate-500">
                        <span>自动 OCR 处理中</span>
                        <span>
                          {autoOcrSummary.completed}/{autoOcrSummary.total}
                        </span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full rounded-full bg-indigo-600 transition-all"
                          style={{
                            width: `${autoOcrSummary.total ? Math.max(8, Math.round((autoOcrSummary.completed / autoOcrSummary.total) * 100)) : 8}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                  {uploadErrors.length > 0 && (
                    <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-500">
                        OCR 异常
                      </p>
                      <div className="mt-2 space-y-1 text-xs leading-5 text-rose-700">
                        {uploadErrors.slice(0, 3).map((error) => (
                          <p key={error}>{error}</p>
                        ))}
                        {uploadErrors.length > 3 && <p>还有 {uploadErrors.length - 3} 条未展开</p>}
                      </div>
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-900 mb-4 uppercase tracking-wider">设置</h3>
                  <div className="flex flex-col gap-2">
                    <span className="text-xs text-slate-400">返回数量</span>
                    <div className="flex flex-wrap gap-2">
                      {resultCountOptions.map(count => (
                        <button key={count} onClick={() => setResultLimit(count)} className={`px-3 py-1 rounded-md text-xs font-bold ${resultLimit === count ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                          {count}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </aside>

              {/* 右侧结果区 */}
              <section className="lg:col-span-3">
                <div className="mb-6 flex items-end justify-between">
                  <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                    {isGalleryMode ? "您的画廊" : "检索结果"}
                  </h2>
                  <div className="flex items-center gap-3">
                    {!isGalleryMode && (
                      <button
                        onClick={() => setResults([])}
                        className="text-xs font-medium text-slate-500 hover:text-indigo-600"
                      >
                        返回画廊
                      </button>
                    )}
                    <button
                      onClick={() => loadGallery()}
                      className="text-xs font-medium text-slate-500 hover:text-indigo-600"
                    >
                      刷新
                    </button>
                    <span className="text-sm text-slate-400">{displayItems.length} 项</span>
                  </div>
                </div>

                {displayItems.length === 0 && !loadingSearch && !loadingGallery && (
                  <div className="flex flex-col items-center justify-center rounded-3xl border-2 border-dashed border-slate-200 bg-slate-50 py-20 text-center">
                    <p className="text-slate-400">
                      {isGalleryMode ? "画廊为空，请先上传图片" : "暂无搜索结果"}
                    </p>
                  </div>
                )}

                {loadingGallery && isGalleryMode && (
                  <div className="flex flex-col items-center justify-center rounded-3xl border border-slate-200 bg-slate-50 py-16 text-center">
                    <p className="text-slate-400">正在加载您的画廊...</p>
                  </div>
                )}

                {!isGalleryMode && (
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
                    {displayItems.map((item) => (
                      <PhotoCard
                        key={item.image.id}
                        item={item}
                        onOpenDetail={openDetail}
                        onSimilarSearch={handleSimilarSearch}
                      />
                    ))}
                  </div>
                )}

                {isGalleryMode && displayItems.length > 0 && (
                  <div className="space-y-8">
                    {recentGalleryItems.length > 0 && (
                      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                        <div className="mb-4 flex items-center justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                              Recent
                            </p>
                            <h3 className="mt-1 text-lg font-bold text-slate-900">最近上传</h3>
                          </div>
                          <span className="text-xs text-slate-400">最近 4 张</span>
                        </div>
                        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                          {recentGalleryItems.map((item) => (
                            <PhotoCard
                              key={`recent-${item.image.id}`}
                              item={item}
                              onOpenDetail={openDetail}
                              onSimilarSearch={handleSimilarSearch}
                            />
                          ))}
                        </div>
                      </section>
                    )}

                    {galleryGroups.map((group) => (
                      <section key={group.label}>
                        <div className="mb-4 flex items-center justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
                              Timeline
                            </p>
                            <h3 className="mt-1 text-lg font-bold text-slate-900">{group.label}</h3>
                          </div>
                          <span className="text-xs text-slate-400">{group.items.length} 张</span>
                        </div>
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
                          {group.items.map((item) => (
                            <PhotoCard
                              key={item.image.id}
                              item={item}
                              onOpenDetail={openDetail}
                              onSimilarSearch={handleSimilarSearch}
                            />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {selectedItem && (
          <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/45 backdrop-blur-[2px]">
            <button
              type="button"
              aria-label="关闭详情"
              className="absolute inset-0 cursor-default"
              onClick={closeDetail}
            />
            <aside className="relative z-10 flex h-full w-full max-w-2xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    图片详情
                  </p>
                  <h2 className="mt-1 text-lg font-bold text-slate-900 line-clamp-1">
                    {selectedItem.image.filename}
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    {selectedItemIndex >= 0 ? `${selectedItemIndex + 1} / ${displayItems.length}` : ""}
                  </p>
                </div>
                <div className="ml-4 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={goToPrevDetail}
                    disabled={!hasPrevItem}
                    className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 18l-6-6 6-6" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={goToNextDetail}
                    disabled={!hasNextItem}
                    className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={closeDetail}
                    className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                <div className="overflow-hidden rounded-3xl bg-slate-100 shadow-sm">
                  <div className="relative aspect-[4/3] w-full">
                    <Image
                      src={resolveBackendAssetUrl(selectedItem.image.original_url || selectedItem.image.thumbnail_url)}
                      alt={selectedItem.image.filename}
                      fill
                      unoptimized
                      className="object-cover"
                    />
                  </div>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  <DetailStat label="文件名" value={selectedItem.image.filename} />
                  <DetailStat label="上传时间" value={formatDateTimeLabel(selectedItem.image.created_at)} />
                  <DetailStat label="尺寸" value={`${selectedItem.image.width ?? "?"} x ${selectedItem.image.height ?? "?"}`} />
                  <DetailStat label="格式" value={selectedItem.image.format ?? "未知"} />
                  <DetailStat label="文件大小" value={formatFileSize(selectedItem.image.file_size)} />
                  <DetailStat
                    label="编码状态"
                    value={selectedItem.image.embedding_ready ? "已完成" : "处理中"}
                  />
                  <DetailStat
                    label="检索匹配度"
                    value={
                      selectedItem.similarity_score == null
                        ? "当前为图库视图"
                        : `${(selectedItem.similarity_score * 100).toFixed(1)}%`
                    }
                  />
                  <DetailStat label="图片 ID" value={selectedItem.image.id} mono />
                </div>

                <section className="mt-6 rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                        OCR
                      </p>
                      <h3 className="mt-1 text-base font-bold text-slate-900">图中文字识别</h3>
                      <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">
                        适合菜单、路牌、票据、海报、截图等场景。当前识别在浏览器本地执行，识别结果会自动回写到账号图库，供后续 OCR 搜索使用。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRunOcr(selectedItem)}
                      disabled={selectedOcrState?.loading}
                      className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {selectedOcrState?.loading
                        ? `识别中 ${Math.round((selectedOcrState.progress || 0) * 100)}%`
                        : selectedOcrCache
                          ? "重新查看结果"
                          : "识别图中文字"}
                    </button>
                  </div>

                  {selectedOcrState?.loading && (
                    <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3">
                      <div className="flex items-center justify-between gap-3 text-sm text-slate-600">
                        <span>{formatOcrStage(selectedOcrState.stage)}</span>
                        <span>{Math.round((selectedOcrState.progress || 0) * 100)}%</span>
                      </div>
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-indigo-600 transition-all"
                          style={{ width: `${Math.max(6, Math.round((selectedOcrState.progress || 0) * 100))}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {selectedOcrState?.error && (
                    <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                      {selectedOcrState.error}
                    </div>
                  )}

                  {!selectedOcrState?.loading && hasSelectedOcrResult && (
                    <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                          识别结果
                        </p>
                        <span className="text-xs text-slate-400">
                          {selectedOcrCache || selectedOcrState?.text ? "已完成" : ""}
                        </span>
                      </div>
                      <pre className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
                        {selectedOcrCache || selectedOcrState?.text || "未识别到明显文字"}
                      </pre>
                      <p className="mt-3 text-xs leading-5 text-slate-400">
                        这段文字已经保存到当前账号下，之后使用“图中文字入口”搜索时会参与匹配。
                      </p>
                    </div>
                  )}
                </section>
              </div>

              <div className="border-t border-slate-200 px-5 py-4">
                <div className="grid gap-3 sm:grid-cols-4">
                  <button
                    type="button"
                    onClick={goToPrevDetail}
                    disabled={!hasPrevItem}
                    className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    上一张
                  </button>
                  <button
                    type="button"
                    onClick={goToNextDetail}
                    disabled={!hasNextItem}
                    className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    下一张
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSimilarSearch(selectedItem.image.id)}
                    className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
                  >
                    查相似图
                  </button>
                  <a
                    href={resolveBackendAssetUrl(selectedItem.image.original_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-xl border border-slate-200 px-4 py-3 text-center text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    打开原图
                  </a>
                </div>
              </div>
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}

// 辅助函数保持一致
function dedupeSearchResults(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item?.image?.filename}-${item?.image?.file_size}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function getStatusTone(status) {
  if (status.includes("失败") || status.includes("错误")) return "error";
  if (status.includes("成功") || status.includes("就绪") || status.includes("完成")) return "success";
  if (status.includes("中") || status.includes("检查")) return "loading";
  return "idle";
}

function formatDateLabel(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatMonthLabel(value) {
  if (!value) return "未知时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知时间";
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月`;
}

function formatDateTimeLabel(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return `${formatDateLabel(value)} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "未知";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatOcrStage(stage) {
  const mapping = {
    "loading tesseract core": "正在加载 OCR 核心",
    "initializing tesseract": "正在初始化 OCR 引擎",
    "loading language traineddata": "正在加载文字识别数据",
    "initializing api": "正在初始化识别接口",
    "recognizing text": "正在识别图中文字",
    done: "识别完成",
  };
  return mapping[stage] || stage || "准备 OCR 引擎";
}

function sleep(delayMs) {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}

function DetailStat({ label, value, mono = false }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className={`mt-2 text-sm text-slate-800 break-all ${mono ? "font-mono" : "font-medium"}`}>
        {value}
      </p>
    </div>
  );
}

function PhotoCard({ item, onOpenDetail, onSimilarSearch }) {
  const imageUrl = resolveBackendAssetUrl(item.image.thumbnail_url);

  return (
    <article
      onClick={() => onOpenDetail(item)}
      className="group relative overflow-hidden rounded-2xl bg-slate-100 shadow-sm transition hover:-translate-y-1 hover:shadow-xl cursor-pointer"
    >
      <div className="aspect-[4/5] w-full">
        {imageUrl && (
          <Image
            src={imageUrl}
            alt={item.image.filename}
            width={300}
            height={400}
            unoptimized
            className="h-full w-full object-cover"
          />
        )}
      </div>
      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 transition-opacity group-hover:opacity-100">
        <div className="p-4">
          <p className="line-clamp-1 text-xs font-bold text-white/90">{item.image.filename}</p>
          <p className="mt-1 text-[10px] text-white/70">
            {item.similarity_score == null
              ? `${item.image.width ?? "?"} x ${item.image.height ?? "?"}`
              : `匹配度: ${(item.similarity_score * 100).toFixed(1)}%`}
          </p>
          <p className="mt-1 text-[10px] text-white/60">{formatDateLabel(item.image.created_at)}</p>
          <div className="mt-3 flex gap-2">
            <button
              onClick={(event) => {
                event.stopPropagation();
                onSimilarSearch(item.image.id);
              }}
              className="flex-1 rounded-md bg-white/20 px-2 py-1.5 text-[10px] font-bold text-white backdrop-blur-md hover:bg-white/30"
            >
              找相似
            </button>
            <a
              onClick={(event) => event.stopPropagation()}
              href={resolveBackendAssetUrl(item.image.original_url)}
              target="_blank"
              rel="noreferrer"
              className="rounded-md bg-indigo-600 px-2 py-1.5 text-[10px] font-bold text-white hover:bg-indigo-500"
            >
              原图
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}

function persistSession(token) { if (typeof window !== "undefined") window.localStorage.setItem(TOKEN_STORAGE_KEY, token); }
function readStoredToken() { return typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_STORAGE_KEY) || "" : ""; }
function clearStoredToken() { if (typeof window !== "undefined") window.localStorage.removeItem(TOKEN_STORAGE_KEY); }
