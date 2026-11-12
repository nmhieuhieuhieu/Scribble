import { useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { useAppStore } from '../stores/appStore';
import { getSettings, saveSettings, diagnose, fetchLLMModels, getLocalModelStatus } from '../lib/api';
import type { LocalModelStatus } from '../lib/api';
import { t } from '../i18n';
import { CustomSelect } from './CustomSelect';
import { useToast } from './Toast';
import { IconAlert, IconCheck, IconCheckCircle, IconClose, IconEye, IconEyeOff, IconMic, IconNib, IconSettings, IconSpinner } from './icons/scribble-icons';

export function SettingsPanel() {
    const { setSettingsOpen, lang } = useAppStore();
    const { showToast } = useToast();
    const [modelStatus, setModelStatus] = useState<LocalModelStatus | null>(null);
    const [llmKey, setLlmKey] = useState('');
    const [llmUrl, setLlmUrl] = useState('');
    const [llmModel, setLlmModel] = useState('');
    const [llmProvider, setLlmProvider] = useState('compatible');
    const [llmModelOptions, setLlmModelOptions] = useState<string[]>([]);
    const [fetchingModels, setFetchingModels] = useState(false);

    const [saving, setSaving] = useState(false);
    const [testRunning, setTestRunning] = useState(false);
    const [sttResult, setSttResult] = useState<{ok: boolean; msg: string} | null>(null);
    const [llmResult, setLlmResult] = useState<{ok: boolean; msg: string} | null>(null);
    const [showLlmKey, setShowLlmKey] = useState(false);
    type SettingsTab = 'stt' | 'ai';
    const [settingsTab, setSettingsTab] = useState<SettingsTab>('stt');
    const [closing, setClosing] = useState(false);
    const tabsBarRef = useRef<HTMLDivElement>(null);
    const [pillStyle, setPillStyle] = useState<{ left: number; width: number } | null>(null);

    const closePanel = () => {
        if (closing) return;
        setClosing(true);
        setTimeout(() => {
            setSettingsOpen(false);
        }, 350);
    };

    useEffect(() => {
        const bar = tabsBarRef.current;
        if (!bar) return;
        const activeBtn = bar.querySelector<HTMLElement>('.settings-tab.active');
        if (activeBtn) {
            setPillStyle({ left: activeBtn.offsetLeft, width: activeBtn.offsetWidth });
        }
    }, [settingsTab, lang]);

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') closePanel();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    });

    useEffect(() => { loadSettings(); }, []);

    const loadSettings = async () => {
        try {
            const s = await getSettings();
            if (s.llm_api_key) setLlmKey('••••••••');
            if (s.llm_base_url) setLlmUrl(s.llm_base_url);
            if (s.llm_model) setLlmModel(s.llm_model);
            if (s.llm_provider) setLlmProvider(s.llm_provider);
        } catch (e) {
            console.warn('[settings] Failed to load settings:', e);
        }
    };

    // Fetch the local model status for Zipformer
    useEffect(() => {
        let active = true;
        const tick = async () => {
            try {
                const s = await getLocalModelStatus('zipformer');
                if (!active) return;
                setModelStatus(s);
            } catch { /* sidecar warming up */ }
        };
        tick();
        return () => { active = false; };
    }, []);

    const handleSave = async () => {
        setSaving(true);
        try {
            await saveSettings(buildSettingsBody());
            // Notify other views that settings changed.
            window.dispatchEvent(new CustomEvent('scribble:settings-saved'));
        } catch (e) { console.warn('[settings] Save failed:', e); }
        setSaving(false);
        closePanel();
    };

    const buildSettingsBody = () => {
        const body: Record<string, unknown> = {};
        body.stt_provider = 'local';
        body.stt_language = 'vi';
        body.local_engine = 'zipformer';
        if (!llmKey.includes('•')) body.llm_api_key = llmKey;
        if (llmProvider === 'compatible') {
            body.llm_base_url = llmUrl;
        }
        body.llm_provider = llmProvider;
        body.llm_model = llmModel;
        return body;
    };

    const handleFetchModels = async () => {
        setFetchingModels(true);
        setLlmModelOptions([]); // clear cả model cũ trước khi fetch
        try {
            const result = await fetchLLMModels(llmProvider, llmKey, llmProvider === 'compatible' ? llmUrl : undefined);
            if (result.error) {
                // Model list giữ nguyên trạng thái rỗng (cũ đã xóa ở bước trên)
                const errMsg = result.error.includes('401')
                    ? (lang === 'vi' ? 'Mã API Key không hợp lệ (401 Unauthorized)' : 'Invalid API Key (401 Unauthorized)')
                    : result.error.includes('404') 
                        ? (lang === 'vi' ? 'Không tìm thấy endpoint (404)' : 'Endpoint not found (404)')
                        : (lang === 'vi' ? `Lỗi lấy model: ${result.error}` : `Fetch error: ${result.error}`);
                showToast(errMsg, 'error');
            } else if (result.models && result.models.length > 0) {
                setLlmModelOptions(result.models);
            } else {
                showToast(lang === 'vi' ? 'Không tìm thấy model nào' : 'No models found', 'warning');
            }
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            showToast(lang === 'vi' ? `Lỗi kết nối: ${msg}` : `Connection error: ${msg}`, 'error');
        }
        setFetchingModels(false);
    };

    const testAll = async () => {
        setTestRunning(true);
        setSttResult(null);
        setLlmResult(null);
        try {
            await saveSettings(buildSettingsBody());
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 15000);
            try {
                const r = await diagnose(lang, controller.signal);
                clearTimeout(timeout);
                // Offline: backend short-circuits both checks with the same
                // clean message. Surface it once as a toast so the user isn't
                // staring at two identical "no internet" rows.
                if (r.network?.online === false) {
                    const offlineMsg = lang === 'vi'
                        ? 'Không có kết nối mạng — kiểm tra Internet rồi thử lại'
                        : 'No internet connection — check your network and retry';
                    showToast(offlineMsg, 'error');
                }
                setSttResult({ ok: r.stt?.status === 'ok', msg: r.stt?.message || 'Error' });
                setLlmResult({ ok: r.llm?.status === 'ok', msg: r.llm?.message || 'Error' });
            } catch (e: unknown) {
                clearTimeout(timeout);
                const msg = (e instanceof DOMException && e.name === 'AbortError')
                    ? (lang === 'vi' ? 'Quá thời gian (15s)' : 'Timeout (15s)')
                    : (lang === 'vi' ? 'Không kết nối được' : 'Cannot connect');
                setSttResult({ ok: false, msg });
                setLlmResult({ ok: false, msg });
            }
        } catch (e) {
            console.warn('[settings] Test failed:', e);
            setSttResult({ ok: false, msg: 'Cannot save' });
            setLlmResult({ ok: false, msg: 'Cannot save' });
        }
        setTestRunning(false);
    };

    const hasLlmKey = llmKey.length > 0;
    const hasLlmModel = llmModel.length > 0;
    // Model can only be picked once the prerequisite credential is present:
    // an API key for hosted providers, or a Base URL for the OpenAI-compatible
    // self-host case (key optional there). Without it, fetching models would
    // 401 — so the Model field is disabled until then.
    const canConfigureModel = llmProvider === 'compatible'
        ? llmUrl.trim().length > 0
        : hasLlmKey;

    const ConfigBadge = ({ ok, optional = false }: { ok: boolean; optional?: boolean }) => {
        if (ok) {
            return (
                <span className="config-status-badge configured">
                    {lang === 'vi' ? '✓ Đã cấu hình' : '✓ Configured'}
                </span>
            );
        }
        // Optional + unset → neutral "Tùy chọn", not an alarming warning.
        if (optional) {
            return (
                <span className="config-status-badge optional-unset">
                    {t('optional_label', lang)}
                </span>
            );
        }
        return (
            <span className="config-status-badge missing">
                {lang === 'vi' ? '⚠ Chưa cấu hình' : '⚠ Not set'}
            </span>
        );
    };

    // One connection-test result row: a colored status badge, the category
    // (Giọng nói / Trợ lý AI), then the message — left-aligned with real gaps
    // so nothing crowds the icon and long messages wrap cleanly.
    const renderTestRow = (label: string, result: { ok: boolean; msg: string }) => (
        <div className={`settings-test-result-row ${result.ok ? 'ok' : 'fail'}`}>
            <span className="settings-test-result-icon" aria-hidden>
                {result.ok ? (
                    <IconCheck size={12} strokeWidth={2.7} />
                ) : (
                    <IconClose size={12} strokeWidth={2.7} />
                )}
            </span>
            <span className="settings-test-result-label">{label}</span>
            <span className="settings-test-result-msg">{result.msg}</span>
        </div>
    );

    return (
        <div className={`settings-overlay${closing ? ' is-closing' : ''}`} onClick={closePanel}>
            <div className={`settings-panel${closing ? ' is-closing' : ''}`} onClick={(e) => e.stopPropagation()}>
                <div className="settings-panel-header">
                    <h2 className="settings-panel-title">
                        <IconSettings size={16} />
                        <span>{t('settings', lang)}</span>
                    </h2>
                    <button className="settings-close-btn" onClick={closePanel}>
                        <IconClose size={16} />
                    </button>
                </div>

                <div className="settings-panel-body tabbed">
                    {/* ── Top-level tabs: STT / AI / General (16-tabs-sliding.md) ── */}
                    <div
                        ref={tabsBarRef}
                        className={`settings-tabs${pillStyle ? ' has-pill' : ''}`}
                        role="tablist"
                        aria-label={lang === 'vi' ? 'Nhóm cài đặt' : 'Settings groups'}
                    >
                        {pillStyle && (
                            <span
                                className="settings-tabs-pill"
                                aria-hidden="true"
                                style={{
                                    transform: `translateX(${pillStyle.left}px)`,
                                    width: `${pillStyle.width}px`,
                                }}
                            />
                        )}
                        {([
                            { id: 'stt', label: lang === 'vi' ? 'Giọng nói' : 'Speech', icon: <IconMic size={15} /> },
                            { id: 'ai', label: lang === 'vi' ? 'Trợ lý AI' : 'AI Assistant', icon: <IconNib size={15} /> },
                        ] as { id: SettingsTab; label: string; icon: ReactNode }[]).map((tab) => (
                            <button
                                key={tab.id}
                                role="tab"
                                aria-selected={settingsTab === tab.id}
                                className={`settings-tab${settingsTab === tab.id ? ' active' : ''}`}
                                onClick={() => setSettingsTab(tab.id)}
                            >
                                {tab.icon}
                                <span className="settings-tab-label">{tab.label}</span>
                            </button>
                        ))}
                    </div>

                    {settingsTab === 'stt' && (<>
                    {/* ── STT Section ── */}
                    <div className="settings-section">
                        <div className="settings-section-header">
                            <div className="settings-section-title">
                                <IconMic size={16} />
                                <span>{t('voice_recognition', lang)}</span>
                            </div>
                            <div className="settings-section-desc">{t('voice_recognition_desc', lang)}</div>
                        </div>

                        <div className="settings-section-body">
                            <div className="setting-group setting-group--full">
                                <div className="setting-label">{lang === 'vi' ? 'Mô hình nhận diện giọng nói' : 'Speech recognition model'}</div>
                                <div className="setting-provider-tabs">
                                    <div className="provider-tab active" style={{ cursor: 'default' }}>
                                        <strong>Zipformer 30M</strong>
                                        <span className="provider-tab-desc">
                                            {lang === 'vi' ? 'Local (offline) • Có sẵn • Tiếng Việt • Rất nhẹ' : 'Local (offline) • Built-in • Vietnamese • Very light'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="setting-warning">
                                <IconAlert size={14} />
                                <span>
                                    {lang === 'vi'
                                        ? 'Chạy hoàn toàn trên máy — miễn phí, không cần mạng, riêng tư. Chỉ hỗ trợ tiếng Việt; ghi âm realtime và Upload file đều được.'
                                        : 'Runs entirely on your device — free, offline, private. Vietnamese only; works for both realtime recording and file upload.'}
                                </span>
                            </div>

                            <div className="setting-group setting-group--full" style={{ marginTop: 8 }}>
                                <div className="setting-label" style={{ color: '#16a34a' }}>
                                    ✓ {lang === 'vi' ? 'Sẵn sàng dùng offline' : 'Ready to use offline'}
                                </div>
                                <div className="setting-hint" style={{ opacity: 0.7, marginTop: 4 }}>
                                    {modelStatus?.display_name || 'Sherpa Zipformer VN (30M, int8)'} · {modelStatus?.size_mb || 32}MB
                                </div>
                            </div>
                        </div>
                    </div>
                    </>)}

                    {settingsTab === 'ai' && (<>
                    {/* ── LLM Section ── */}
                    <div className="settings-section">
                        <div className="settings-section-header">
                            <div className="settings-section-title">
                                <IconNib size={16} />
                                <span>{t('ai_section', lang)}</span>
                                <span className="settings-section-optional-pill">{t('optional_label', lang)}</span>
                            </div>
                            <div className="settings-section-desc">{t('ai_hint', lang)}</div>
                        </div>

                        <div className="settings-section-body">

                        {/* Provider Dropdown */}
                        <div className="setting-group">
                            <div className="setting-label" style={{ textTransform: 'uppercase' }}>{lang === 'vi' ? 'Nhà cung cấp' : 'Provider'}</div>
                            <CustomSelect
                                options={[
                                    { value: 'openai',     label: 'OpenAI' },
                                    { value: 'mistral',    label: 'Mistral AI' },
                                    { value: 'groq',       label: 'Groq' },
                                    { value: 'deepseek',   label: 'DeepSeek' },
                                    { value: 'openrouter', label: 'OpenRouter' },
                                    { value: 'gemini',     label: 'Google Gemini' },
                                    { value: 'compatible', label: lang === 'vi' ? 'Tương thích OpenAI' : 'OpenAI Compatible' },
                                ]}
                                value={llmProvider}
                                onChange={(val) => { setLlmProvider(val); setLlmModelOptions([]); }}
                            />
                        </div>

                        {/* API Key */}
                        <div className="setting-group setting-group--full">
                            <div className="setting-label">
                                API Key
                                <ConfigBadge ok={hasLlmKey} optional />
                            </div>
                            <div className="setting-input-wrap">
                                <input type={showLlmKey ? 'text' : 'password'} className="setting-input" value={llmKey} onChange={(e) => { setLlmKey(e.target.value); setLlmModelOptions([]); }} placeholder="sk-xxx" />
                                <button type="button" className="setting-eye-btn" onClick={() => setShowLlmKey(v => !v)} aria-label="toggle key">
                                    <span className="t-icon-swap" data-state={showLlmKey ? 'b' : 'a'}>
                                        <span className="t-icon" data-icon="a"><IconEye size={14} /></span>
                                        <span className="t-icon" data-icon="b"><IconEyeOff size={14} /></span>
                                    </span>
                                </button>
                            </div>
                        </div>

                        {/* Custom URL — only for compatible */}
                        {llmProvider === 'compatible' && (
                            <div className="setting-group setting-group--full">
                                <div className="setting-label" style={{ textTransform: 'uppercase' }}>Base URL</div>
                                <input type="text" className="setting-input" value={llmUrl} onChange={(e) => { setLlmUrl(e.target.value); setLlmModelOptions([]); }} placeholder="https://api.example.com/v1" />
                            </div>
                        )}

                        {/* Model — disabled until the credential exists; auto-fetches on open */}
                        <div className="setting-group">
                            <div className="setting-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', textTransform: 'uppercase' }}>
                                <span>Model <ConfigBadge ok={hasLlmModel && canConfigureModel} optional /></span>
                            </div>
                            <CustomSelect
                                options={fetchingModels
                                    ? [{ value: '', label: lang === 'vi' ? 'Đang tải...' : 'Loading...' }]
                                    : !canConfigureModel
                                        ? [{ value: '', label: llmProvider === 'compatible'
                                            ? (lang === 'vi' ? '-- Nhập Base URL trước --' : '-- Enter Base URL first --')
                                            : (lang === 'vi' ? '-- Nhập API Key trước --' : '-- Enter API Key first --') }]
                                        : (llmModelOptions.length > 0
                                            ? llmModelOptions.map(m => ({ value: m, label: m }))
                                            : (llmModel ? [{ value: llmModel, label: llmModel }] : [{ value: '', label: lang === 'vi' ? '-- Bấm để tải model --' : '-- Click to load --' }]))
                                }
                                value={fetchingModels ? '' : (canConfigureModel ? llmModel : '')}
                                onChange={setLlmModel}
                                disabled={fetchingModels || !canConfigureModel}
                                onOpen={() => {
                                    if (canConfigureModel && llmModelOptions.length === 0 && !fetchingModels) {
                                        handleFetchModels();
                                    }
                                }}
                            />
                            <div className="setting-hint" style={{ marginTop: '6px' }}>
                                {!canConfigureModel
                                    ? (llmProvider === 'compatible'
                                        ? (lang === 'vi' ? 'Nhập Base URL để chọn model' : 'Enter Base URL to pick a model')
                                        : (lang === 'vi' ? 'Nhập API Key để chọn model' : 'Enter API Key to pick a model'))
                                    : llmModelOptions.length > 0
                                        ? `${llmModelOptions.length} ${lang === 'vi' ? 'model khả dụng' : 'models available'}`
                                        : t('ai_model_hint', lang)}
                            </div>
                        </div>
                        </div>
                    </div>

                    {/* ── Unified Test Connection ── */}
                    <div className="settings-section settings-test-section span-full" style={{ marginTop: '16px' }}>
                        <div className="settings-test-head">
                            <span className="settings-test-label">
                                {lang === 'vi'
                                    ? 'Kiểm tra API key đã hoạt động chưa'
                                    : 'Verify your API keys'}
                            </span>
                            <button className="settings-test-btn" onClick={testAll} disabled={testRunning}>
                                {testRunning ? (
                                    <IconSpinner size={16} className="spin" strokeWidth={2.25} />
                                ) : (
                                    <IconCheckCircle size={16} />
                                )}
                                <span>{testRunning ? t('testing', lang) : t('test_all_connections', lang)}</span>
                            </button>
                        </div>
                        {(sttResult || llmResult) && (
                            <div className="settings-test-results">
                                {sttResult && renderTestRow(t('test_result_stt', lang), sttResult)}
                                {llmResult && renderTestRow(t('test_result_llm', lang), llmResult)}
                            </div>
                        )}
                    </div>
                    </>)}
                </div>

                <div className="settings-panel-footer">
                    <div className="settings-footer-actions">
                        <button className="action-btn primary" onClick={handleSave} disabled={saving}>
                            <IconCheck size={14} />
                            <span>{saving ? '...' : t('save_settings', lang)}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
