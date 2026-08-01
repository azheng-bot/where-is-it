import { FormEvent, useEffect, useState } from "react";
import {
  IconAdjustments, IconArrowUp, IconBox, IconCamera, IconChevronRight, IconCircleCheck,
  IconCircleDashed, IconEye, IconHistory, IconLayoutGrid, IconMicrophone, IconPlayerStop,
  IconSearch, IconSettings, IconSparkles, IconVolume, IconX, IconChevronLeft,
} from "@tabler/icons-react";
import type { CatalogObject, QueryResult } from "@where-is-it/contracts";
import { askQuestion, getLocations, getObjects, getRoomState, renameObject, transcribeAudio } from "./api";

type Page = "search" | "catalog" | "locations" | "history";

function formatTime(value?: string) {
  if (!value) return "尚未记录";
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit", month: "numeric", day: "numeric" }).format(new Date(value));
}

function StatusBadge({ state }: { state: string }) {
  const names: Record<string, string> = {
    currently_detected: "当前检测", not_currently_detected: "当前未检测", identity_uncertain: "身份待确认",
    clarification: "需要确认", not_found: "未找到",
  };
  return <span className={"status status--" + state}><i />{names[state] ?? state}</span>;
}

function boxStyle(boundingBox?: [number, number, number, number]) {
  if (!boundingBox) return undefined;
  const [left, top, width, height] = boundingBox;
  return { left: `${left * 100}%`, top: `${top * 100}%`, width: `${width * 100}%`, height: `${height * 100}%` };
}

function CameraPreview({ frameUrl, streamUrl, boundingBox }: { frameUrl?: string; streamUrl?: string; boundingBox?: [number, number, number, number] }) {
  const [streamFailed, setStreamFailed] = useState(false);
  useEffect(() => setStreamFailed(false), [streamUrl]);
  return <section className="camera-card">
    <div className="camera-image">{streamUrl && !streamFailed ? <video autoPlay muted loop playsInline poster={frameUrl} aria-label="模拟室内监控直播" onError={() => setStreamFailed(true)}><source src={streamUrl} type="video/mp4" /></video> : <img src={frameUrl ?? "http://127.0.0.1:8001/api/camera/frame"} alt="卧室摄像头预览" />}{boundingBox && <span className="camera-box" style={boxStyle(boundingBox)} />}<span className="camera-label"><IconCamera size={14} /> LIVE</span></div>
  </section>;
}
function EvidenceModal({ result, onClose }: { result: QueryResult; onClose: () => void }) {
  if (!result.evidence || !result.object) return null;
  return <div className="dialog-backdrop" onMouseDown={onClose}>
    <section className="evidence-dialog" role="dialog" aria-modal="true" aria-label="检测依据" onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span className="eyebrow">检测依据</span><h2>{result.object.name}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><IconX /></button></header>
      <div className="evidence-image"><img src={result.evidence.image_url} alt={result.object.name + "的观测画面"} /><span className="bounding-box" style={boxStyle(result.evidence.bounding_box)} /></div>
      <footer><div><strong>{result.object.current_location?.name ?? result.object.last_location?.name}</strong><span>{formatTime(result.evidence.observed_at)}</span></div><span className="metadata">目标边界已标注</span></footer>
    </section>
  </div>;
}

function SearchPage({ frameUrl, streamUrl }: { frameUrl?: string; streamUrl?: string }) {
  const [question, setQuestion] = useState("我的钥匙在哪里");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [transcript, setTranscript] = useState("");
  async function submit(event?: FormEvent, text?: string) {
    event?.preventDefault();
    const query = (text ?? question).trim();
    if (!query) return;
    setLoading(true); setError("");
    try { setResult(await askQuestion(query)); } catch (reason) { setError(reason instanceof Error ? reason.message : "查询失败，请重试。"); } finally { setLoading(false); }
  }
  function listen() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("当前浏览器不支持语音输入，请直接输入问题。");
      return;
    }
    setListening(true);
    setTranscript("");
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : undefined });
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => { setListening(false); setError("录音失败，请改用文字输入。"); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setListening(false);
        try {
          const result = await transcribeAudio(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
          setTranscript(result.text);
          setQuestion(result.text);
          submit(undefined, result.text);
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "语音转写失败");
        }
      };
      recorder.start();
      window.setTimeout(() => { if (recorder.state !== "inactive") recorder.stop(); }, 1800);
    }).catch(() => { setListening(false); setError("未获得麦克风权限，仍可使用文字输入。"); });
  }
  function speak() { if (result && "speechSynthesis" in window) { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.answer)); } }
  const submitObject = (name: string) => { const text = "我的" + name + "在哪里"; setQuestion(text); submit(undefined, text); };
  return <main className="page search-page"><div className="search-layout search-layout--focus"><section className="search-main">
    <form className="question-form" onSubmit={submit}><IconSearch /><input value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="输入要查找的物品" placeholder="输入要找的物品" /><button type="button" className={"microphone" + (listening ? " is-listening" : "")} onClick={listen} aria-label="使用麦克风"><IconMicrophone /></button><button className="send-button" aria-label="提交问题"><IconArrowUp /></button></form>
    {error && <div className="inline-message inline-message--error"><IconCircleDashed />{error}</div>}
    {transcript && <div className="transcript-message">转写：{transcript}</div>}
    {loading && <section className="answer-skeleton" aria-label="正在查询"><div /><div /><div /></section>}
    {result && !loading && <section className="answer-panel">
      <div className="answer-panel__headline"><div><StatusBadge state={result.status} /><h2>{result.answer}</h2></div>{result.object && <span className="answer-time">{formatTime(result.object.observed_at)}</span>}</div>
      {result.status === "clarification" && <div className="clarification"><span>请选择具体物品</span><div>{result.clarification_options?.map((item) => <button key={item.object_id} onClick={() => submitObject(item.name)}>{item.name}<IconChevronRight size={16} /></button>)}</div></div>}
      {result.predictions.length > 0 && <div className="prediction-area"><div className="prediction-list">{result.predictions.map((prediction) => <article key={prediction.location.location_id}><div><span className={"confidence confidence--" + prediction.confidence}>推测</span><strong>{prediction.location.name}</strong><p>{prediction.basis}</p></div><span className="score">{Math.round(prediction.score * 100)}%</span></article>)}</div></div>}
      <div className="answer-actions">{result.evidence && <button onClick={() => setShowEvidence(true)}><IconEye size={17} />依据</button>}<button onClick={speak}><IconVolume size={17} />播报</button><button onClick={() => window.speechSynthesis?.cancel()} aria-label="停止播报"><IconPlayerStop size={17} /></button></div>
    </section>}
    {!result && !loading && <div className="search-hint">输入问题即可开始查找。</div>}
  </section><aside className="search-aside"><CameraPreview frameUrl={frameUrl} streamUrl={streamUrl} boundingBox={result?.evidence?.bounding_box} /></aside></div>
  {showEvidence && result && <EvidenceModal result={result} onClose={() => setShowEvidence(false)} />}</main>;
}
function CatalogPage({ objects, refresh }: { objects: CatalogObject[]; refresh: () => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("");
  async function save(item: CatalogObject) { try { await renameObject(item.object_id, draft, item.aliases); setEditing(null); setNotice("已更新物品名称，身份与历史记录保持不变。"); refresh(); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "保存失败"); } }
  return <main className="page"><header className="page-header"><div><span className="eyebrow">物品目录</span><h1>房间已记住的具体物品</h1><p>每个物品都有稳定身份；名称可修改，历史不会断开。</p></div><span className="count-badge">{objects.length} 个物品</span></header>{notice && <div className="inline-message"><IconCircleCheck />{notice}</div>}<section className="catalog-grid">{objects.map((item) => <article className="catalog-card" key={item.object_id}><div className="catalog-card__top"><span className="object-avatar"><IconBox size={21} /></span><StatusBadge state={item.state} /></div>{editing === item.object_id ? <div className="edit-name"><input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} /><div><button onClick={() => save(item)}>保存</button><button onClick={() => setEditing(null)}>取消</button></div></div> : <><h2>{item.name}</h2><p className="system-name">系统识别：{item.system_name}</p></>}<div className="catalog-card__location"><span>{item.state === "currently_detected" ? "当前" : "最后"}位置</span><strong>{item.current_location?.name ?? item.last_location?.name ?? "待确认"}</strong><small>{item.current_location?.relation ?? item.last_location?.relation ?? "身份仍需确认"}</small></div><div className="card-actions"><span>{Math.round(item.confidence * 100)}% 识别置信</span><button onClick={() => { setEditing(item.object_id); setDraft(item.name); }}>改名</button></div></article>)}</section></main>;
}

function LocationsPage({ frameUrl, streamUrl }: { frameUrl?: string; streamUrl?: string }) {
  const [locations, setLocations] = useState<Array<{ location_id: string; name: string; item_count: number }>>([]);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => { getLocations().then(setLocations).catch(() => setLocations([])); }, []);
  return <main className="page"><header className="page-header"><div><span className="eyebrow">位置目录</span><h1>让房间有可解释的区域</h1><p>位置名称与区域可以调整，既有物品关联和历史保持不变。</p></div><button className="secondary-button"><IconAdjustments size={18} />编辑区域</button></header><div className="location-layout"><CameraPreview frameUrl={frameUrl} streamUrl={streamUrl} /><section className="location-list"><span className="eyebrow">已确认位置</span>{locations.map((location) => <button key={location.location_id} className={selected === location.location_id ? "is-selected" : ""} onClick={() => setSelected(location.location_id)}><span className="location-icon"><IconBox size={18} /></span><span><strong>{location.name}</strong><small>当前关联 {location.item_count} 个物品</small></span><IconChevronRight size={18} /></button>)}{locations.length === 0 && <p className="empty-list">位置目录暂不可用。</p>}</section></div></main>;
}

function App() {
  const [page, setPage] = useState<Page>("search");
  const [objects, setObjects] = useState<CatalogObject[]>([]);
  const [frameUrl, setFrameUrl] = useState<string>();
  const [streamUrl, setStreamUrl] = useState<string>();
  const [apiOffline, setApiOffline] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const refresh = () => getObjects().then((data) => { setObjects(data); setApiOffline(false); }).catch(() => setApiOffline(true));
  useEffect(() => { refresh(); getRoomState().then((state) => { setFrameUrl(state.camera.frame_url); setStreamUrl(state.camera.stream_url); }).catch(() => undefined); }, []);
  const nav: Array<{ id: Page; label: string; icon: typeof IconSearch }> = [{ id: "search", label: "查找", icon: IconSearch }, { id: "catalog", label: "物品目录", icon: IconLayoutGrid }, { id: "locations", label: "位置目录", icon: IconBox }, { id: "history", label: "历史记录", icon: IconHistory }];
  return <div className={"app-shell" + (sidebarCollapsed ? " is-sidebar-collapsed" : "")}><aside className="sidebar"><div className="sidebar-head"><button className="brand" onClick={() => setPage("search")}><span className="brand-mark"><IconSearch size={20} /></span><span>在哪里<small>室内物品查找助手</small></span></button><button className="sidebar-toggle" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}><IconChevronLeft size={18} /></button></div><nav>{nav.map((item) => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)} title={item.label}><Icon size={19} /><span>{item.label}</span></button>; })}</nav><div className="sidebar-bottom"><div className="service-state"><span className={apiOffline ? "offline" : ""} /><div><strong>{apiOffline ? "服务离线" : "服务在线"}</strong><small>{apiOffline ? "请启动 API" : "视觉记忆运行中"}</small></div></div></div></aside><header className="mobile-header"><button className="brand-mobile" onClick={() => setPage("search")}><span className="brand-mark"><IconSearch size={18} /></span>在哪里</button><span className="mobile-status"><i />在线</span></header><div className="content">{page === "search" && <SearchPage frameUrl={frameUrl} streamUrl={streamUrl} />}{page === "catalog" && <CatalogPage objects={objects} refresh={refresh} />}{page === "locations" && <LocationsPage frameUrl={frameUrl} streamUrl={streamUrl} />}{page === "history" && <main className="page history-placeholder"><IconHistory size={28} /><h1>历史记录即将就绪</h1><p>首次出现、位置变化与最后观测会在这里按时间呈现。</p><button className="secondary-button" onClick={() => setPage("search")}><IconSearch size={18} />回到查找</button></main>}</div><nav className="mobile-nav">{nav.slice(0, 3).map((item) => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={19} /><span>{item.label}</span></button>; })}</nav></div>;
}

export default App;