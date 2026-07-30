import { FormEvent, useEffect, useState } from "react";
import {
  IconAdjustments, IconArrowUp, IconBox, IconCamera, IconChevronRight, IconCircleCheck,
  IconCircleDashed, IconEye, IconHistory, IconLayoutGrid, IconMicrophone, IconPlayerStop,
  IconSearch, IconSettings, IconSparkles, IconVolume, IconX,
} from "@tabler/icons-react";
import type { CatalogObject, QueryResult } from "@where-is-it/contracts";
import { askQuestion, getLocations, getObjects, renameObject } from "./api";

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

function CameraPreview() {
  return <section className="camera-card">
    <div className="camera-card__top"><span className="eyebrow">实时视图</span><span className="online-dot">摄像头在线</span></div>
    <div className="camera-image"><img src="https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=1400&q=85" alt="卧室书桌摄像头预览" /><span className="camera-label"><IconCamera size={14} /> 卧室摄像头 01</span><span className="camera-box" /></div>
    <div className="camera-card__bottom"><span>最近更新：刚刚</span><span>1280 × 720</span></div>
  </section>;
}

function EvidenceModal({ result, onClose }: { result: QueryResult; onClose: () => void }) {
  if (!result.evidence || !result.object) return null;
  return <div className="dialog-backdrop" onMouseDown={onClose}>
    <section className="evidence-dialog" role="dialog" aria-modal="true" aria-label="检测依据" onMouseDown={(event) => event.stopPropagation()}>
      <header><div><span className="eyebrow">检测依据</span><h2>{result.object.name}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭"><IconX /></button></header>
      <div className="evidence-image"><img src={result.evidence.image_url} alt={result.object.name + "的观测画面"} /><span className="bounding-box" /></div>
      <footer><div><strong>{result.object.current_location?.name ?? result.object.last_location?.name}</strong><span>{formatTime(result.evidence.observed_at)}</span></div><span className="metadata">目标边界已标注</span></footer>
    </section>
  </div>;
}

function SearchPage({ objects }: { objects: CatalogObject[] }) {
  const [question, setQuestion] = useState("我的钥匙在哪里");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  async function submit(event?: FormEvent, text?: string) {
    event?.preventDefault();
    const query = (text ?? question).trim();
    if (!query) return;
    setLoading(true); setError("");
    try { setResult(await askQuestion(query)); } catch (reason) { setError(reason instanceof Error ? reason.message : "查询失败，请重试。"); } finally { setLoading(false); }
  }
  function listen() {
    if (!navigator.mediaDevices?.getUserMedia) { setError("当前浏览器不支持麦克风录音，请直接输入问题。"); return; }
    setListening(true);
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => { stream.getTracks().forEach((track) => track.stop()); setQuestion("我的钥匙在哪里"); setListening(false); }).catch(() => { setListening(false); setError("未获得麦克风权限，但你仍可以使用文字输入。"); });
  }
  function speak() {
    if (result && "speechSynthesis" in window) { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.answer)); }
  }
  const submitObject = (name: string) => { const text = "我的" + name + "在哪里"; setQuestion(text); submit(undefined, text); };
  return <main className="page search-page"><div className="search-layout"><section className="search-main">
    <div className="page-intro"><span className="eyebrow">问一问房间</span><h1>物品的位置，<br />基于看得见的证据。</h1><p>系统会明确区分当前检测、最后出现与推测位置。</p></div>
    <form className="question-form" onSubmit={submit}><IconSearch /><input value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="输入要查找的物品" placeholder="例如：我的钥匙在哪里" /><button type="button" className={"microphone" + (listening ? " is-listening" : "")} onClick={listen} aria-label="使用麦克风"><IconMicrophone /></button><button className="send-button" aria-label="提交问题"><IconArrowUp /></button></form>
    {error && <div className="inline-message inline-message--error"><IconCircleDashed />{error}</div>}
    {loading && <section className="answer-skeleton" aria-label="正在查询"><div /><div /><div /></section>}
    {result && !loading && <section className="answer-panel">
      <div className="answer-panel__headline"><div><StatusBadge state={result.status} /><h2>{result.answer}</h2></div>{result.object && <span className="answer-time">{formatTime(result.object.observed_at)}</span>}</div>
      {result.status === "clarification" && <div className="clarification"><span>请选择具体物品</span><div>{result.clarification_options?.map((item) => <button key={item.object_id} onClick={() => submitObject(item.name)}>{item.name}<IconChevronRight size={16} /></button>)}</div></div>}
      {result.object && <div className="fact-grid">
        <div className="fact"><span>确定事实</span><strong>{result.status === "currently_detected" ? result.object.current_location?.name : result.object.last_location?.name ?? "暂无"}</strong><p>{result.status === "currently_detected" ? result.object.current_location?.relation : "最后一次确定位置"}</p></div>
        <div className="fact"><span>观测时间</span><strong>{formatTime(result.object.observed_at)}</strong><p>{result.status === "currently_detected" ? "在新鲜度窗口内" : "不代表当前位置"}</p></div>
        {result.evidence && <button className="fact fact--action" onClick={() => setShowEvidence(true)}><span>可核验依据</span><strong>查看画面</strong><p><IconEye size={15} />目标标记与时间</p></button>}
      </div>}
      {result.predictions.length > 0 && <div className="prediction-area"><div className="section-head"><div><span className="eyebrow">推测位置</span><p>以下候选不是已检测到的位置</p></div></div><div className="prediction-list">{result.predictions.map((prediction) => <article key={prediction.location.location_id}><div><span className={"confidence confidence--" + prediction.confidence}>{prediction.confidence === "high" ? "较高" : "中等"}可能</span><strong>{prediction.location.name}</strong><p>{prediction.basis}</p></div><span className="score">{Math.round(prediction.score * 100)}%</span></article>)}</div></div>}
      <div className="answer-actions"><button onClick={speak}><IconVolume size={18} />播报</button><button onClick={() => window.speechSynthesis?.cancel()}><IconPlayerStop size={18} />停止</button></div>
    </section>}
    {!result && !loading && <section className="empty-answer"><IconSparkles /><div><strong>输入物品名称开始查找</strong><p>例如“我的眼镜在哪里”或“黑色水杯在哪”。</p></div></section>}
    <section className="recent-section"><div className="section-head"><div><span className="eyebrow">已记住的物品</span><p>自动扫描后建立，可随时更正名称。</p></div></div><div className="object-chips">{objects.slice(0, 4).map((item) => <button key={item.object_id} onClick={() => submitObject(item.name)}><span className="chip-icon"><IconBox size={17} /></span>{item.name}</button>)}</div></section>
  </section><aside className="search-aside"><CameraPreview /><section className="engine-card"><div className="engine-card__icon"><IconSparkles size={20} /></div><div><strong>视觉记忆已就绪</strong><p>目录与状态会在后台持续更新，查询不等待视觉推理。</p></div></section></aside></div>
  {showEvidence && result && <EvidenceModal result={result} onClose={() => setShowEvidence(false)} />}</main>;
}

function CatalogPage({ objects, refresh }: { objects: CatalogObject[]; refresh: () => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState("");
  async function save(item: CatalogObject) { try { await renameObject(item.object_id, draft, item.aliases); setEditing(null); setNotice("已更新物品名称，身份与历史记录保持不变。"); refresh(); } catch (reason) { setNotice(reason instanceof Error ? reason.message : "保存失败"); } }
  return <main className="page"><header className="page-header"><div><span className="eyebrow">物品目录</span><h1>房间已记住的具体物品</h1><p>每个物品都有稳定身份；名称可修改，历史不会断开。</p></div><span className="count-badge">{objects.length} 个物品</span></header>{notice && <div className="inline-message"><IconCircleCheck />{notice}</div>}<section className="catalog-grid">{objects.map((item) => <article className="catalog-card" key={item.object_id}><div className="catalog-card__top"><span className="object-avatar"><IconBox size={21} /></span><StatusBadge state={item.state} /></div>{editing === item.object_id ? <div className="edit-name"><input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} /><div><button onClick={() => save(item)}>保存</button><button onClick={() => setEditing(null)}>取消</button></div></div> : <><h2>{item.name}</h2><p className="system-name">系统识别：{item.system_name}</p></>}<div className="catalog-card__location"><span>{item.state === "currently_detected" ? "当前" : "最后"}位置</span><strong>{item.current_location?.name ?? item.last_location?.name ?? "待确认"}</strong><small>{item.current_location?.relation ?? item.last_location?.relation ?? "身份仍需确认"}</small></div><div className="card-actions"><span>{Math.round(item.confidence * 100)}% 识别置信</span><button onClick={() => { setEditing(item.object_id); setDraft(item.name); }}>改名</button></div></article>)}</section></main>;
}

function LocationsPage() {
  const [locations, setLocations] = useState<Array<{ location_id: string; name: string; item_count: number }>>([]);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => { getLocations().then(setLocations).catch(() => setLocations([])); }, []);
  return <main className="page"><header className="page-header"><div><span className="eyebrow">位置目录</span><h1>让房间有可解释的区域</h1><p>位置名称与区域可以调整，既有物品关联和历史保持不变。</p></div><button className="secondary-button"><IconAdjustments size={18} />编辑区域</button></header><div className="location-layout"><CameraPreview /><section className="location-list"><span className="eyebrow">已确认位置</span>{locations.map((location) => <button key={location.location_id} className={selected === location.location_id ? "is-selected" : ""} onClick={() => setSelected(location.location_id)}><span className="location-icon"><IconBox size={18} /></span><span><strong>{location.name}</strong><small>当前关联 {location.item_count} 个物品</small></span><IconChevronRight size={18} /></button>)}{locations.length === 0 && <p className="empty-list">位置目录暂不可用。</p>}</section></div></main>;
}

function App() {
  const [page, setPage] = useState<Page>("search");
  const [objects, setObjects] = useState<CatalogObject[]>([]);
  const [apiOffline, setApiOffline] = useState(false);
  const refresh = () => getObjects().then((data) => { setObjects(data); setApiOffline(false); }).catch(() => setApiOffline(true));
  useEffect(() => { refresh(); }, []);
  const nav: Array<{ id: Page; label: string; icon: typeof IconSearch }> = [{ id: "search", label: "查找", icon: IconSearch }, { id: "catalog", label: "物品目录", icon: IconLayoutGrid }, { id: "locations", label: "位置目录", icon: IconBox }, { id: "history", label: "历史记录", icon: IconHistory }];
  return <div className="app-shell"><aside className="sidebar"><button className="brand" onClick={() => setPage("search")}><span className="brand-mark"><IconSearch size={20} /></span><span>在哪里<small>室内物品查找助手</small></span></button><nav>{nav.map((item) => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={19} />{item.label}</button>; })}</nav><div className="sidebar-bottom"><button><IconSettings size={18} />设置</button><div className="service-state"><span className={apiOffline ? "offline" : ""} /><div><strong>{apiOffline ? "演示数据" : "服务已连接"}</strong><small>{apiOffline ? "请启动 API 服务" : "视觉记忆运行中"}</small></div></div></div></aside><header className="mobile-header"><button className="brand-mobile" onClick={() => setPage("search")}><span className="brand-mark"><IconSearch size={18} /></span>在哪里</button><span className="mobile-status"><i />在线</span></header><div className="content">{page === "search" && <SearchPage objects={objects} />}{page === "catalog" && <CatalogPage objects={objects} refresh={refresh} />}{page === "locations" && <LocationsPage />}{page === "history" && <main className="page history-placeholder"><IconHistory size={28} /><h1>历史记录即将就绪</h1><p>首次出现、位置变化与最后观测会在这里按时间呈现。</p><button className="secondary-button" onClick={() => setPage("search")}><IconSearch size={18} />回到查找</button></main>}</div><nav className="mobile-nav">{nav.slice(0, 3).map((item) => { const Icon = item.icon; return <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><Icon size={19} /><span>{item.label}</span></button>; })}</nav></div>;
}

export default App;