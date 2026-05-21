import { Fragment, useEffect, useState } from "react";
import { api, type LogDetail, type LogRow } from "../api/client";

const PAGE_SIZE = 100;

function formatBody(text: string | null): string {
  if (!text) return "";
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

export function Logs() {
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, LogDetail>>({});
  const [detailLoading, setDetailLoading] = useState<number | null>(null);

  async function load() {
    try {
      setError(null);
      const r = await api.logs({
        provider: provider || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setLogs(r.logs);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, page]);

  async function toggleRow(id: number) {
    if (expanded === id) {
      setExpanded(null);
      return;
    }
    setExpanded(id);
    if (!details[id]) {
      setDetailLoading(id);
      try {
        const r = await api.logDetail(id);
        setDetails((prev) => ({ ...prev, [id]: r.log }));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setDetailLoading(null);
      }
    }
  }

  async function clearOld() {
    const days = prompt("删除多少天之前的日志？", "7");
    if (!days) return;
    const before = Date.now() - Number(days) * 24 * 60 * 60 * 1000;
    try {
      const r = await api.deleteLogsBefore(before);
      alert(`已删除 ${r.removed} 条`);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div>
      <h2>聊天日志</h2>

      {error && (
        <div className="banner err">
          <span className="ic">!</span>
          <div className="body">{error}</div>
        </div>
      )}

      <div className="row">
        <span style={{ color: "var(--muted)", fontSize: 13 }}>过滤：</span>
        <select value={provider} onChange={(e) => { setProvider(e.target.value); setPage(0); }}>
          <option value="">全部</option>
          <option value="mimo">mimo</option>
          <option value="deepseek">deepseek</option>
        </select>
        <button onClick={() => load()} className="secondary">
          刷新
        </button>
        <span className="grow" />
        <button onClick={clearOld} className="secondary">
          清理旧日志…
        </button>
      </div>

      {logs.length > 0 ? (
        <>
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>Provider</th>
                <th>Client model</th>
                <th>Upstream model</th>
                <th>端点</th>
                <th>状态</th>
                <th style={{ textAlign: "right" }}>Prompt tokens</th>
                <th style={{ textAlign: "right" }}>Completion tokens</th>
                <th style={{ textAlign: "right" }}>合计 tokens</th>
                <th style={{ textAlign: "right" }}>工具</th>
                <th style={{ textAlign: "right" }}>耗时</th>
                <th>错误</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => {
                const isOpen = expanded === l.id;
                const detail = details[l.id];
                return (
                  <Fragment key={l.id}>
                    <tr
                      onClick={() => toggleRow(l.id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td>
                        <span style={{ marginRight: 6, color: "var(--muted)" }}>
                          {isOpen ? "▾" : "▸"}
                        </span>
                        {new Date(l.ts).toLocaleString()}
                      </td>
                      <td>
                        <span className="tag">{l.provider_id}</span>
                      </td>
                      <td className="mono">{l.client_model}</td>
                      <td className="mono">{l.upstream_model}</td>
                      <td className="mono">{l.endpoint}</td>
                      <td>
                        <span className={`tag ${l.status_code >= 400 ? "err" : "ok"}`}>
                          {l.status_code}
                          {l.stream ? " · stream" : ""}
                        </span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {l.prompt_tokens ?? "—"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {l.completion_tokens ?? "—"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {l.total_tokens ?? "—"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {l.tool_call_count && l.tool_call_count > 0 ? l.tool_call_count : "—"}
                      </td>
                      <td style={{ textAlign: "right" }}>{l.duration_ms} ms</td>
                      <td className="mono" style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={l.error_snippet ?? ""}>
                        {l.error_code ?? ""}
                        {l.error_snippet ? `: ${l.error_snippet}` : ""}
                      </td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={12} style={{ background: "var(--bg-soft, #f7f7f9)", padding: 12 }}>
                          {detailLoading === l.id && !detail ? (
                            <div style={{ color: "var(--muted)" }}>加载中…</div>
                          ) : detail ? (
                            <div style={{ display: "grid", gap: 12 }}>
                              <BodyBlock title="请求内容" body={detail.request_body} />
                              <BodyBlock title="响应内容" body={detail.response_body} />
                            </div>
                          ) : (
                            <div style={{ color: "var(--muted)" }}>无内容</div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 12 }}>
            <button
              className="secondary"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ← 上一页
            </button>
            <span style={{ color: "var(--muted)" }}>第 {page + 1} 页</span>
            <button
              className="secondary"
              disabled={logs.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页 →
            </button>
          </div>
        </>
      ) : (
        <div className="empty">暂无日志</div>
      )}
    </div>
  );
}

function BodyBlock({ title, body }: { title: string; body: string | null }) {
  if (!body) {
    return (
      <div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
        <div style={{ color: "var(--muted)", fontSize: 13 }}>（未捕获）</div>
      </div>
    );
  }
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontWeight: 600 }}>{title}</span>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{body.length.toLocaleString()} chars</span>
      </div>
      <pre
        className="mono"
        style={{
          maxHeight: 360,
          overflow: "auto",
          background: "var(--bg, #fff)",
          border: "1px solid var(--border, #ddd)",
          borderRadius: 4,
          padding: 8,
          fontSize: 12,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          margin: 0,
        }}
      >
        {formatBody(body)}
      </pre>
    </div>
  );
}
