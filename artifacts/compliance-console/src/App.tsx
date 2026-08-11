import { type ReactNode, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Archive,
  ArrowUpRight,
  Bot,
  Check,
  ClipboardCheck,
  CircleDot,
  Database,
  FileCheck2,
  FileText,
  FolderOpen,
  LayoutDashboard,
  Loader2,
  Menu,
  Network,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
  Zap,
} from 'lucide-react';
import { Link, Route, Switch, useLocation } from 'wouter';

import {
  useAnalyzeCompliance,
  useCreateComplianceIssue,
  useDeleteDocument,
  useGetDashboard,
  useHealthCheck,
  useListAgentRuns,
  useListAuditReports,
  useListComplianceIssues,
  useListDocuments,
  useListOpenApiTools,
  useUpdateComplianceIssue,
  useUploadDocument,
  getListComplianceIssuesQueryKey,
  getListDocumentsQueryKey,
  type AgentRun,
  type AssistantResponse,
  type ComplianceIssue,
  type ComplianceIssueUpdate,
  type Document,
} from '@workspace/api-client-react';

import { ErrorBoundary } from '@/components/error-boundary';
import NotFound from '@/pages/not-found';
import './index.css';

const queryClient = new QueryClient();

/* -------------------------------------------------------------------------- */
/* Navigation                                                                  */
/* -------------------------------------------------------------------------- */

const navItems = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/documents', label: 'Knowledge base', icon: FolderOpen },
  { href: '/assistant', label: 'Compliance assistant', icon: Bot },
  { href: '/issues', label: 'Issue register', icon: AlertTriangle },
  { href: '/reports', label: 'Audit reports', icon: ClipboardCheck },
  { href: '/activity', label: 'Agent activity', icon: Network },
];

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value : [];
}

function fmtDate(value?: string | null) {
  if (!value) return '—';

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
}

function fmtTime(value?: string | null) {
  if (!value) return '—';

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
      });
}

/* -------------------------------------------------------------------------- */
/* Shell                                                                       */
/* -------------------------------------------------------------------------- */

function Shell({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  const { data: health } = useHealthCheck();

  const current =
    navItems.find((item) => item.href === location)?.label ??
    'Compliance workspace';

  return (
    <div className="app-shell">
      <aside className="sidebar" data-testid="navigation-sidebar">
        <div className="brand">
          <div className="brand-mark">AR</div>

          <div>
            <div className="brand-name">ARGUS / REG</div>
            <div className="brand-sub">
              banking compliance intelligence
            </div>
          </div>
        </div>

        <button
          className="mobile-menu button button-quiet"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle navigation"
        >
          <Menu size={16} />
        </button>

        <div className={menuOpen ? 'nav open' : 'nav'}>
          <div className="nav-label">Workspace</div>

          {navItems.map(({ href, label, icon: Icon }) => (
            <Link
              href={href}
              key={href}
              className={`nav-link ${
                location === href ? 'active' : ''
              }`}
              data-testid={`link-nav-${label
                .toLowerCase()
                .replaceAll(' ', '-')}`}
            >
              <Icon className="nav-icon" />
              <span>{label}</span>
            </Link>
          ))}
        </div>

        <div className="sidebar-footer">
          <div>
            <span className="health-dot" />
            <span className="health-text">
              {health?.status === 'ok'
                ? 'SYSTEMS OPERATIONAL'
                : 'SYSTEM STATUS'}
            </span>
          </div>

          <div
            className="health-text"
            style={{ marginTop: 8 }}
          >
            Evidence layer · v1.0.0
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="crumb">
            ARGUS / REG
            <span style={{ margin: '0 5px' }}>›</span>
            {current}
          </div>

          <div className="topbar-meta">
            <span className="mono">
              CONTROL ROOM ·{' '}
              {new Date()
                .toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })
                .toUpperCase()}
            </span>

            <div className="avatar">MC</div>
          </div>
        </header>

        {children}
      </main>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Common UI                                                                   */
/* -------------------------------------------------------------------------- */

function PageHead({
  eyebrow,
  title,
  intro,
  action,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        <p className="page-intro">{intro}</p>
      </div>

      {action}
    </div>
  );
}

function LoadingPanel({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card panel" aria-label="Loading">
      <div
        className="skeleton"
        style={{
          width: 150,
          height: 14,
          marginBottom: 18,
        }}
      />

      {Array.from({ length: rows }).map((_, index) => (
        <div
          className="skeleton"
          key={index}
          style={{
            height: 46,
            marginTop: 8,
          }}
        />
      ))}
    </div>
  );
}

function ErrorPanel({
  onRetry,
  message = 'Unable to load this control surface.',
}: {
  onRetry?: () => void;
  message?: string;
}) {
  return (
    <div className="error-state" role="alert">
      <span>
        <AlertTriangle
          size={14}
          style={{
            display: 'inline',
            marginRight: 8,
          }}
        />
        {message}
      </span>

      {onRetry && (
        <button
          className="button button-danger button-small"
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  );
}

function EmptyPanel({
  icon: Icon = Archive,
  message,
}: {
  icon?: typeof Archive;
  message: string;
}) {
  return (
    <div className="empty-state">
      <Icon size={22} />
      <p>{message}</p>
    </div>
  );
}

function StatusChip({ value }: { value?: string | null }) {
  const cls = (value ?? 'unknown')
    .toLowerCase()
    .replaceAll(' ', '_');

  return (
    <span className={`status-chip ${cls}`}>
      {value ?? 'Unknown'}
    </span>
  );
}

function RiskChip({ value }: { value?: string | null }) {
  const cls = (value ?? 'unknown').toLowerCase();

  return (
    <span className={`risk-chip ${cls}`}>
      {value ?? 'Unknown'}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Overview                                                                    */
/* -------------------------------------------------------------------------- */

function Dashboard() {
  const dashboard = useGetDashboard();
  const runs = useListAgentRuns({ limit: 5 });

  if (dashboard.isLoading) {
    return (
      <div className="content">
        <PageHead
          eyebrow="Live control room"
          title="Compliance overview"
          intro="A live view of your institution's evidence coverage, exposure, and audit activity."
        />

        <div className="metric-grid">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              className="card metric-card skeleton"
              key={i}
            />
          ))}
        </div>

        <LoadingPanel />
      </div>
    );
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <div className="content">
        <ErrorPanel
          onRetry={() => dashboard.refetch()}
        />
      </div>
    );
  }

  const d = dashboard.data;

  const recentRuns = asArray<AgentRun>(
    d.recent_runs
  );

  const liveRuns = asArray<AgentRun>(
    runs.data
  );

  const displayedRuns =
    recentRuns.length > 0
      ? recentRuns
      : liveRuns;

  return (
    <div className="content">
      <PageHead
        eyebrow="Live control room"
        title="Compliance overview"
        intro="A live view of your institution's evidence coverage, exposure, and audit activity."
        action={
          <Link
            href="/assistant"
            className="button button-primary"
          >
            <Zap size={14} />
            Run grounded analysis
          </Link>
        }
      />

      <div className="metric-grid">
        <div className="card metric-card">
          <div className="metric-label">
            Compliance score
          </div>

          <div className="metric-value">
            {d.compliance_score}
            <span
              style={{
                fontSize: 18,
                opacity: 0.65,
              }}
            >
              /100
            </span>
          </div>

          <div className="metric-note">
            <ShieldCheck
              size={11}
              style={{
                display: 'inline',
                marginRight: 5,
              }}
            />
            Live assessment
          </div>
        </div>

        <div className="card metric-card">
          <div className="metric-label">
            Open issues
          </div>
          <div className="metric-value">
            {d.open_issues}
          </div>
          <div className="metric-note">
            Across all controls
          </div>
        </div>

        <div className="card metric-card">
          <div className="metric-label">
            High-risk
          </div>
          <div className="metric-value">
            {d.high_risk_issues}
          </div>
          <div className="metric-note">
            Needs attention
          </div>
        </div>

        <div className="card metric-card">
          <div className="metric-label">
            Indexed docs
          </div>
          <div className="metric-value">
            {d.documents_indexed}
          </div>
          <div className="metric-note">
            Evidence sources
          </div>
        </div>

        <div className="card metric-card">
          <div className="metric-label">
            Completed audits
          </div>
          <div className="metric-value">
            {d.completed_audits}
          </div>
          <div className="metric-note">
            Generated reports
          </div>
        </div>
      </div>

      <div className="grid-2">
        <section className="card panel">
          <div className="panel-title">
            <h2>Recent agent runs</h2>

            <Link
              href="/activity"
              className="panel-kicker"
            >
              View activity <ArrowUpRight size={11} />
            </Link>
          </div>

          {runs.isLoading ? (
            <LoadingPanel rows={4} />
          ) : runs.isError ? (
            <ErrorPanel
              onRetry={() => runs.refetch()}
            />
          ) : displayedRuns.length ? (
            <div className="run-list">
              {displayedRuns
                .slice(0, 5)
                .map((run) => (
                  <RunRow
                    key={run.id}
                    run={run}
                  />
                ))}
            </div>
          ) : (
            <EmptyPanel
              icon={Bot}
              message="No agent workflow runs recorded yet."
            />
          )}
        </section>

        <section className="card panel">
          <div className="panel-title">
            <h2>Control posture</h2>
            <span className="panel-kicker">
              Signal summary
            </span>
          </div>

          <div
            style={{
              padding: '8px 0 18px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: 8,
              }}
            >
              <span
                className="muted"
                style={{ fontSize: 12 }}
              >
                Evidence-backed posture
              </span>

              <span className="mono">
                {d.compliance_score}/100
              </span>
            </div>

            <div
              style={{
                height: 8,
                background:
                  'hsl(var(--secondary))',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${Math.max(
                    0,
                    Math.min(
                      100,
                      d.compliance_score
                    )
                  )}%`,
                  background:
                    'hsl(var(--primary))',
                }}
              />
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gap: 11,
              borderTop:
                '1px solid hsl(var(--border))',
              paddingTop: 16,
            }}
          >
            <MiniLine
              label="Open findings"
              value={String(d.open_issues)}
              tone="warn"
            />

            <MiniLine
              label="High / critical exposure"
              value={String(
                d.high_risk_issues
              )}
              tone="danger"
            />

            <MiniLine
              label="Source coverage"
              value={`${d.documents_indexed} documents`}
              tone="good"
            />
          </div>
        </section>
      </div>
    </div>
  );
}

function MiniLine({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 12,
      }}
    >
      <span className="muted">{label}</span>

      <span
        className={`risk-chip ${
          tone === 'danger'
            ? 'high'
            : tone === 'warn'
            ? 'medium'
            : 'low'
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function RunRow({ run }: { run: AgentRun }) {
  return (
    <div className="run-row">
      <div>
        <div className="run-question">
          {run.question}
        </div>

        <div className="run-meta">
          <span>
            {fmtDate(run.started_at)} ·{' '}
            {fmtTime(run.started_at)}
          </span>

          <span>·</span>

          <span className="run-agent">
            {run.current_agent ??
              run.agents_involved?.[0] ??
              'workflow'}
          </span>
        </div>
      </div>

      <StatusChip value={run.status} />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Compliance Assistant                                                        */
/* -------------------------------------------------------------------------- */

function Assistant() {
  const docsQuery = useListDocuments();
  const analysis = useAnalyzeCompliance();

  const [question, setQuestion] =
    useState('');

  const [regulationId, setRegulationId] =
    useState('');

  const [policyId, setPolicyId] =
    useState('');

  const [response, setResponse] =
    useState<AssistantResponse | null>(null);

  const documents = asArray<Document>(
    docsQuery.data
  );

  const regulations = documents.filter(
    (document) =>
      document.category === 'regulation'
  );

  const policies = documents.filter(
    (document) =>
      document.category === 'policy'
  );

  const submit = () => {
    if (
      question.trim().length < 10 ||
      !regulationId
    ) {
      return;
    }

    analysis.mutate(
      {
        data: {
          question: question.trim(),
          regulation_document_id:
            regulationId,
          policy_document_id:
            policyId || null,
        },
      },
      {
        onSuccess: (result) => {
          setResponse(result);
        },
      }
    );
  };

  return (
    <div className="content">
      <PageHead
        eyebrow="Grounded analysis"
        title="Compliance assistant"
        intro="Ask a precise regulatory question. Argus traces its answer to indexed evidence and shows the agents that produced it."
      />

      <div className="assistant-grid">
        <section className="card panel">
          <div className="panel-title">
            <h2>New analysis</h2>
            <span className="panel-kicker">
              RAG + multi-agent
            </span>
          </div>

          <div className="field">
            <label htmlFor="assistant-question">
              Question
            </label>

            <textarea
              id="assistant-question"
              className="textarea assistant-prompt"
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="e.g. Are customer-data access reviews compliant with the applicable regulation?"
            />
          </div>

          <div
            style={{
              display: 'grid',
              gap: 12,
              marginTop: 15,
            }}
          >
            <div className="field">
              <label htmlFor="regulation-document">
                Regulation source
                <span className="muted">
                  {' '}
                  (required)
                </span>
              </label>

              <select
                id="regulation-document"
                className="select"
                value={regulationId}
                onChange={(event) =>
                  setRegulationId(
                    event.target.value
                  )
                }
              >
                <option value="">
                  Select regulation
                </option>

                {regulations.map(
                  (document) => (
                    <option
                      value={document.id}
                      key={document.id}
                    >
                      {document.name}
                    </option>
                  )
                )}
              </select>
            </div>

            <div className="field">
              <label htmlFor="policy-document">
                Policy source
                <span className="muted">
                  {' '}
                  (optional)
                </span>
              </label>

              <select
                id="policy-document"
                className="select"
                value={policyId}
                onChange={(event) =>
                  setPolicyId(
                    event.target.value
                  )
                }
              >
                <option value="">
                  Select policy
                </option>

                {policies.map(
                  (document) => (
                    <option
                      value={document.id}
                      key={document.id}
                    >
                      {document.name}
                    </option>
                  )
                )}
              </select>
            </div>
          </div>

          {!docsQuery.isLoading &&
            regulations.length === 0 && (
              <div
                style={{
                  marginTop: 14,
                }}
              >
                <ErrorPanel
                  message="No regulation document is indexed. Upload a regulation in Knowledge Base first."
                />
              </div>
            )}

          <div
            style={{
              display: 'flex',
              justifyContent:
                'space-between',
              alignItems: 'center',
              marginTop: 19,
            }}
          >
            <span className="mono muted">
              {question.trim().length}/10 min
              characters
            </span>

            <button
              className="button button-primary"
              onClick={submit}
              disabled={
                analysis.isPending ||
                question.trim().length <
                  10 ||
                !regulationId
              }
            >
              {analysis.isPending ? (
                <>
                  <Loader2
                    size={14}
                    className="spin"
                  />
                  Tracing evidence
                </>
              ) : (
                <>
                  <Send size={14} />
                  Submit analysis
                </>
              )}
            </button>
          </div>

          {analysis.isError && (
            <div style={{ marginTop: 14 }}>
              <ErrorPanel
                message="Compliance analysis failed. Check the selected documents and backend logs."
              />
            </div>
          )}
        </section>

        <section className="card panel">
          <div className="panel-title">
            <h2>Analysis result</h2>

            {response && (
              <span className="panel-kicker">
                Run {response.run.id.slice(0, 8)}
              </span>
            )}
          </div>

          {!response &&
          !analysis.isPending ? (
            <EmptyPanel
              icon={FileCheck2}
              message="Your grounded answer, evidence, and risk posture will appear here."
            />
          ) : analysis.isPending ? (
            <LoadingPanel rows={5} />
          ) : response ? (
            <AssistantResult
              response={response}
            />
          ) : null}
        </section>
      </div>
    </div>
  );
}

function AssistantResult({
  response,
}: {
  response: AssistantResponse;
}) {
  const evidence = asArray(
    response.evidence
  );

  const agents = asArray<string>(
    response.agents_involved
  );

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          marginBottom: 18,
        }}
      >
        <StatusChip
          value={response.compliance_status}
        />

        <RiskChip
          value={response.risk_level}
        />
      </div>

      <div className="answer-block">
        <div className="answer">
          {response.answer}
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <div className="panel-title">
          <h2>Evidence cited</h2>

          <span className="panel-kicker">
            {evidence.length} excerpts
          </span>
        </div>

        {evidence.length ? (
          evidence.map((item: any, index) => (
            <div
              className="evidence-item"
              key={`${item.document_id}-${index}`}
            >
              <div className="evidence-meta">
                <span>
                  {item.document_name ??
                    'Source document'}
                </span>

                <span>
                  {item.relevance_score !=
                  null
                    ? `${Math.round(
                        item.relevance_score *
                          100
                      )}% relevant`
                    : item.source_type ??
                      'source'}
                </span>
              </div>

              <p className="evidence-quote">
                “{item.excerpt}”
              </p>

              <div className="evidence-meta">
                <span>
                  {item.source_type ??
                    'document'}
                </span>

                <span>
                  Document ID{' '}
                  {item.document_id ??
                    'not provided'}
                </span>
              </div>
            </div>
          ))
        ) : (
          <EmptyPanel message="No evidence excerpts returned." />
        )}
      </div>

      <div style={{ marginTop: 22 }}>
        <div className="panel-title">
          <h2>Agents involved</h2>
        </div>

        <div className="agent-pills">
          {agents.map((agent) => (
            <span
              className="agent-pill"
              key={agent}
            >
              {agent}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Knowledge Base                                                             */
/* -------------------------------------------------------------------------- */

function Documents() {
  const query = useListDocuments();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();

  const queryClient = useQueryClient();

  const [open, setOpen] =
    useState(false);

  const [category, setCategory] =
    useState<
      'regulation' | 'policy' | 'audit' | 'other'
    >('regulation');

  const [synthetic, setSynthetic] =
    useState(false);

  const [file, setFile] =
    useState<File | null>(null);

  const [search, setSearch] =
    useState('');

  const documents = asArray<Document>(
    query.data
  );
  console.log("DOCUMENT API DATA:", query.data);
  console.log("DOCUMENTS ARRAY:", documents);
  const filteredDocuments = useMemo(
    () =>
      documents.filter(
        (document) =>
          document.name
            .toLowerCase()
            .includes(
              search.toLowerCase()
            ) ||
          document.category
            .toLowerCase()
            .includes(
              search.toLowerCase()
            )
      ),
    [documents, search]
  );

  const submit = () => {
    if (!file) return;

    upload.mutate(
      {
        data: { file },
        params: {
          category,
          is_synthetic: synthetic,
        },
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({
            queryKey:
              getListDocumentsQueryKey(),
          });

          setOpen(false);
          setFile(null);
        },
      }
    );
  };

  return (
    <div className="content">
      <PageHead
        eyebrow="Evidence layer"
        title="Knowledge base"
        intro="Indexed regulations, policies, and audit material available to the compliance agents."
        action={
          <button
            className="button button-primary"
            onClick={() => setOpen(true)}
          >
            <UploadCloud size={14} />
            Index document
          </button>
        }
      />

      <section className="card panel">
        <div className="panel-title">
          <h2>
            Indexed documents{' '}
            <span className="muted">
              ({documents.length})
            </span>
          </h2>

          <div className="toolbar">
            <div
              style={{
                position: 'relative',
              }}
            >
              <Search
                size={13}
                style={{
                  position: 'absolute',
                  left: 9,
                  top: 10,
                }}
              />

              <input
                className="input"
                style={{
                  width: 210,
                  paddingLeft: 28,
                }}
                placeholder="Search evidence"
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value
                  )
                }
              />
            </div>

            <span className="panel-kicker">
              Maintained by controls
            </span>
          </div>
        </div>

        {query.isLoading ? (
          <LoadingPanel rows={5} />
        ) : query.isError ? (
          <ErrorPanel
            onRetry={() => query.refetch()}
          />
        ) : filteredDocuments.length ===
          0 ? (
          <EmptyPanel
            icon={Database}
            message={
              search
                ? 'No indexed documents match that search.'
                : 'No documents are indexed yet. Add your first evidence source.'
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Category</th>
                  <th>State</th>
                  <th>Chunks</th>
                  <th>Added</th>
                  <th />
                </tr>
              </thead>

              <tbody>
                {filteredDocuments.map(
                  (document) => (
                    <DocumentRow
                      key={document.id}
                      doc={document}
                      deleting={
                        remove.isPending
                      }
                      onDelete={() => {
                        if (
                          window.confirm(
                            `Delete ${document.name}?`
                          )
                        ) {
                          remove.mutate(
                            {
                              documentId:
                                document.id,
                            },
                            {
                              onSuccess: () =>
                                queryClient.invalidateQueries(
                                  {
                                    queryKey:
                                      getListDocumentsQueryKey(),
                                  }
                                ),
                            }
                          );
                        }
                      }}
                    />
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {open && (
        <div
          className="dialog-backdrop"
          role="presentation"
        >
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
          >
            <div className="dialog-head">
              <div>
                <div className="eyebrow">
                  Evidence intake
                </div>

                <h2>Index a document</h2>
              </div>

              <button
                className="icon-button"
                onClick={() =>
                  setOpen(false)
                }
                aria-label="Close upload dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className="field">
              <label>File</label>

              <label
                className="file-drop"
                htmlFor="document-file"
              >
                <UploadCloud size={20} />

                <p>
                  {file
                    ? file.name
                    : 'Choose a PDF, DOCX, or TXT file'}
                </p>

                <span>
                  {file
                    ? `${(
                        file.size /
                        1024 /
                        1024
                      ).toFixed(
                        2
                      )} MB · ready to index`
                    : 'The source will be chunked and made searchable'}
                </span>

                <input
                  id="document-file"
                  type="file"
                  accept=".pdf,.docx,.txt,application/pdf,text/plain"
                  hidden
                  onChange={(event) =>
                    setFile(
                      event.target.files?.[0] ??
                        null
                    )
                  }
                />
              </label>
            </div>

            <div
              className="form-grid"
              style={{ marginTop: 16 }}
            >
              <div className="field">
                <label>Category</label>

                <select
                  className="select"
                  value={category}
                  onChange={(event) =>
                    setCategory(
                      event.target
                        .value as typeof category
                    )
                  }
                >
                  <option value="regulation">
                    Regulation
                  </option>
                  <option value="policy">
                    Policy
                  </option>
                  <option value="audit">
                    Audit material
                  </option>
                  <option value="other">
                    Other
                  </option>
                </select>
              </div>

              <div className="field">
                <label>Source label</label>

                <select
                  className="select"
                  value={
                    synthetic
                      ? 'synthetic'
                      : 'official'
                  }
                  onChange={(event) =>
                    setSynthetic(
                      event.target.value ===
                        'synthetic'
                    )
                  }
                >
                  <option value="official">
                    Official / production
                  </option>
                  <option value="synthetic">
                    Synthetic test data
                  </option>
                </select>
              </div>
            </div>

            {upload.isError && (
              <div style={{ marginTop: 14 }}>
                <ErrorPanel
                  message="Document upload failed. Check the backend response."
                />
              </div>
            )}

            <div className="dialog-actions">
              <button
                className="button button-quiet"
                onClick={() =>
                  setOpen(false)
                }
              >
                Cancel
              </button>

              <button
                className="button button-primary"
                onClick={submit}
                disabled={
                  !file || upload.isPending
                }
              >
                {upload.isPending ? (
                  <>
                    <Loader2 size={14} />
                    Indexing
                  </>
                ) : (
                  <>
                    <UploadCloud size={14} />
                    Index document
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DocumentRow({
  doc,
  onDelete,
  deleting,
}: {
  doc: Document;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <tr>
      <td>
        <div className="primary-text">
          <FileText
            size={14}
            style={{
              display: 'inline',
              verticalAlign: '-3px',
              marginRight: 7,
            }}
          />
          {doc.name}
        </div>

        <div
          className="muted mono"
          style={{ marginTop: 5 }}
        >
          {doc.document_type}
          {doc.is_synthetic
            ? ' · synthetic'
            : ''}
        </div>
      </td>

      <td>
        <span className="mono">
          {doc.category}
        </span>
      </td>

      <td>
        <StatusChip value={doc.status} />
      </td>

      <td className="mono">
        {doc.chunk_count}
      </td>

      <td className="mono">
        {fmtDate(
          doc.indexed_at ??
            doc.created_at
        )}
      </td>

      <td>
        <button
          className="button button-danger button-small"
          onClick={onDelete}
          disabled={deleting}
        >
          <Trash2 size={12} />
          Delete
        </button>
      </td>
    </tr>
  );
}

/* -------------------------------------------------------------------------- */
/* Issues                                                                      */
/* -------------------------------------------------------------------------- */

function Issues() {
  const query = useListComplianceIssues();
  const update = useUpdateComplianceIssue();
  const create =
    useCreateComplianceIssue();

  const queryClient = useQueryClient();

  const [filter, setFilter] =
    useState('');

  const [open, setOpen] =
    useState(false);

  const [finding, setFinding] =
    useState('');

  const [regulation, setRegulation] =
    useState('');

  const [risk, setRisk] =
    useState('MEDIUM');

  const [recommendation, setRecommendation] =
    useState('');

  const issues = asArray<ComplianceIssue>(
    query.data
  );

  const filteredIssues =
    issues.filter(
      (issue) =>
        !filter ||
        issue.status === filter
    );

  const updateIssue = (
    id: string,
    data: ComplianceIssueUpdate
  ) => {
    update.mutate(
      {
        issueId: id,
        data,
      },
      {
        onSuccess: () =>
          queryClient.invalidateQueries({
            queryKey:
              getListComplianceIssuesQueryKey(),
          }),
      }
    );
  };

  const createIssue = () => {
    if (
      !finding.trim() ||
      !regulation.trim() ||
      !recommendation.trim()
    ) {
      return;
    }

    create.mutate(
      {
        data: {
          finding,
          regulation,
          risk: risk as
            | 'LOW'
            | 'MEDIUM'
            | 'HIGH'
            | 'CRITICAL',
          recommendation,
        },
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({
            queryKey:
              getListComplianceIssuesQueryKey(),
          });

          setOpen(false);
          setFinding('');
          setRegulation('');
          setRecommendation('');
        },
      }
    );
  };

  return (
    <div className="content">
      <PageHead
        eyebrow="Control remediation"
        title="Issue register"
        intro="Review, triage, and update findings with an operational recommendation and an accountable status."
        action={
          <button
            className="button button-primary"
            onClick={() => setOpen(true)}
          >
            <Plus size={14} />
            Record issue
          </button>
        }
      />

      <section className="card panel">
        <div className="panel-title">
          <h2>
            Findings{' '}
            <span className="muted">
              ({issues.length})
            </span>
          </h2>

          <select
            className="select"
            style={{ width: 150 }}
            value={filter}
            onChange={(event) =>
              setFilter(
                event.target.value
              )
            }
          >
            <option value="">
              All statuses
            </option>
            <option value="OPEN">
              Open
            </option>
            <option value="IN_REVIEW">
              In review
            </option>
            <option value="REMEDIATED">
              Remediated
            </option>
            <option value="ACCEPTED">
              Accepted
            </option>
          </select>
        </div>

        {query.isLoading ? (
          <LoadingPanel rows={5} />
        ) : query.isError ? (
          <ErrorPanel
            onRetry={() => query.refetch()}
          />
        ) : filteredIssues.length ===
          0 ? (
          <EmptyPanel
            icon={ShieldCheck}
            message={
              filter
                ? 'No findings match this status.'
                : 'No compliance issues have been recorded.'
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Finding</th>
                  <th>Regulation</th>
                  <th>Risk</th>
                  <th>Status</th>
                  <th>Recommendation</th>
                  <th>Updated</th>
                </tr>
              </thead>

              <tbody>
                {filteredIssues.map(
                  (issue) => (
                    <IssueRow
                      issue={issue}
                      key={issue.id}
                      onUpdate={updateIssue}
                      pending={
                        update.isPending
                      }
                    />
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {open && (
        <div className="dialog-backdrop">
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
          >
            <div className="dialog-head">
              <div>
                <div className="eyebrow">
                  Control register
                </div>
                <h2>
                  Record a compliance issue
                </h2>
              </div>

              <button
                className="icon-button"
                onClick={() =>
                  setOpen(false)
                }
              >
                <X size={18} />
              </button>
            </div>

            <div className="form-grid">
              <div className="field full">
                <label>Finding</label>

                <textarea
                  className="textarea"
                  value={finding}
                  onChange={(event) =>
                    setFinding(
                      event.target.value
                    )
                  }
                />
              </div>

              <div className="field">
                <label>Regulation</label>

                <input
                  className="input"
                  value={regulation}
                  onChange={(event) =>
                    setRegulation(
                      event.target.value
                    )
                  }
                />
              </div>

              <div className="field">
                <label>Risk</label>

                <select
                  className="select"
                  value={risk}
                  onChange={(event) =>
                    setRisk(
                      event.target.value
                    )
                  }
                >
                  <option>LOW</option>
                  <option>MEDIUM</option>
                  <option>HIGH</option>
                  <option>CRITICAL</option>
                </select>
              </div>

              <div className="field full">
                <label>
                  Recommendation
                </label>

                <textarea
                  className="textarea"
                  value={recommendation}
                  onChange={(event) =>
                    setRecommendation(
                      event.target.value
                    )
                  }
                />
              </div>
            </div>

            {create.isError && (
              <div style={{ marginTop: 14 }}>
                <ErrorPanel />
              </div>
            )}

            <div className="dialog-actions">
              <button
                className="button button-quiet"
                onClick={() =>
                  setOpen(false)
                }
              >
                Cancel
              </button>

              <button
                className="button button-primary"
                disabled={create.isPending}
                onClick={createIssue}
              >
                {create.isPending
                  ? 'Saving'
                  : 'Record issue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function IssueRow({
  issue,
  onUpdate,
  pending,
}: {
  issue: ComplianceIssue;
  onUpdate: (
    id: string,
    data: ComplianceIssueUpdate
  ) => void;
  pending: boolean;
}) {
  return (
    <tr>
      <td style={{ minWidth: 210 }}>
        <div className="primary-text">
          {issue.finding}
        </div>

        <div
          className="muted mono"
          style={{ marginTop: 6 }}
        >
          Created {fmtDate(issue.created_at)}
        </div>
      </td>

      <td>
        <span className="mono">
          {issue.regulation}
        </span>
      </td>

      <td>
        <select
          className="select"
          style={{ width: 105 }}
          value={issue.risk}
          onChange={(event) =>
            onUpdate(issue.id, {
              risk: event.target
                .value as ComplianceIssueUpdate['risk'],
            })
          }
          disabled={pending}
        >
          <option>LOW</option>
          <option>MEDIUM</option>
          <option>HIGH</option>
          <option>CRITICAL</option>
        </select>
      </td>

      <td>
        <select
          className="select"
          style={{ width: 120 }}
          value={issue.status}
          onChange={(event) =>
            onUpdate(issue.id, {
              status: event.target
                .value as ComplianceIssueUpdate['status'],
            })
          }
          disabled={pending}
        >
          <option>OPEN</option>
          <option>IN_REVIEW</option>
          <option>REMEDIATED</option>
          <option>ACCEPTED</option>
        </select>
      </td>

      <td style={{ minWidth: 230 }}>
        <div
          className="muted"
          style={{
            lineHeight: 1.45,
            marginBottom: 8,
          }}
        >
          {issue.recommendation}
        </div>

        <button
          className="button button-quiet button-small"
          onClick={() => {
            const next =
              window.prompt(
                'Update recommendation',
                issue.recommendation
              );

            if (next !== null) {
              onUpdate(issue.id, {
                recommendation: next,
              });
            }
          }}
        >
          <Settings2 size={11} />
          Edit
        </button>
      </td>

      <td className="mono">
        {fmtDate(issue.updated_at)}
      </td>
    </tr>
  );
}

/* -------------------------------------------------------------------------- */
/* Reports                                                                     */
/* -------------------------------------------------------------------------- */

function Reports() {
  const query =
    useListAuditReports();

  const [expanded, setExpanded] =
    useState<string | null>(null);

  const reports = asArray(
    query.data
  );

  return (
    <div className="content">
      <PageHead
        eyebrow="Audit output"
        title="Audit reports"
        intro="Generated audit narratives and findings, formatted for review and export."
      />

      <div
        style={{
          display: 'grid',
          gap: 12,
        }}
      >
        {query.isLoading ? (
          <LoadingPanel rows={4} />
        ) : query.isError ? (
          <ErrorPanel
            onRetry={() => query.refetch()}
          />
        ) : reports.length === 0 ? (
          <div className="card panel">
            <EmptyPanel
              icon={ClipboardCheck}
              message="No audit reports have been generated yet."
            />
          </div>
        ) : (
          reports.map((report: any) => (
            <section
              className="card report-card"
              key={report.id}
            >
              <div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    marginBottom: 10,
                  }}
                >
                  <StatusChip
                    value={report.status}
                  />

                  <span className="mono muted">
                    {fmtDate(
                      report.created_at
                    )}{' '}
                    · by{' '}
                    {report.generated_by}
                  </span>
                </div>

                <h2 className="report-title">
                  {report.title}
                </h2>

                <p className="report-summary">
                  {report.summary}
                </p>

                {expanded === report.id && (
                  <ul className="report-findings">
                    {asArray(
                      report.findings
                    ).map(
                      (
                        finding: any,
                        index: number
                      ) => (
                        <li key={index}>
                          {Object.entries(
                            finding
                          ).map(
                            ([
                              key,
                              value,
                            ]) => (
                              <span
                                key={key}
                              >
                                <strong>
                                  {key}:
                                </strong>{' '}
                                {String(
                                  value
                                )}{' '}
                              </span>
                            )
                          )}
                        </li>
                      )
                    )}
                  </ul>
                )}
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems:
                    'flex-start',
                  gap: 8,
                }}
              >
                <button
                  className="button button-quiet button-small"
                  onClick={() =>
                    setExpanded(
                      expanded ===
                        report.id
                        ? null
                        : report.id
                    )
                  }
                >
                  {expanded ===
                  report.id
                    ? 'Collapse'
                    : 'View findings'}
                </button>

                <button
                  className="button button-primary button-small"
                  onClick={() =>
                    window.print()
                  }
                >
                  <ArrowUpRight size={11} />
                  Export
                </button>
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Agent Activity                                                              */
/* -------------------------------------------------------------------------- */

function Activity() {
  const query =
    useListAgentRuns({
      limit: 100,
    });

  const tools =
    useListOpenApiTools();

  const runs = asArray<AgentRun>(
    query.data
  );
  console.log(
    "ACTIVITY RESULT:",
    JSON.stringify(runs[0]?.result, null, 2)
  );
  const availableTools =
    Array.isArray(tools.data?.tools)
      ? tools.data.tools
      : [];

  return (
    <div className="content">
      <PageHead
        eyebrow="Trace ledger"
        title="Agent activity"
        intro="A transparent record of every grounded workflow, its active agent, and its outcome."
        action={
          <button
            className="button button-quiet"
            onClick={() => query.refetch()}
          >
            <RefreshCw size={14} />
            Refresh ledger
          </button>
        }
      />

      <div className="grid-2">
        <section className="card panel">
          <div className="panel-title">
            <h2>Workflow runs</h2>

            <span className="panel-kicker">
              {runs.length} recorded
            </span>
          </div>

          {query.isLoading ? (
            <LoadingPanel rows={6} />
          ) : query.isError ? (
            <ErrorPanel
              onRetry={() => query.refetch()}
            />
          ) : runs.length === 0 ? (
            <EmptyPanel
              icon={Network}
              message="No workflow runs recorded yet."
            />
          ) : (
            <div className="timeline">
              {runs.map((run) => (
                <ActivityRow
                  key={run.id}
                  run={run}
                />
              ))}
            </div>
          )}
        </section>

        <section className="card panel">
          <div className="panel-title">
            <h2>Agent surface</h2>
            <span className="panel-kicker">
              Available tools
            </span>
          </div>

          {tools.isLoading ? (
            <LoadingPanel rows={3} />
          ) : tools.isError ? (
            <ErrorPanel
              onRetry={() => tools.refetch()}
            />
          ) : availableTools.length ? (
            <div className="agent-pills">
              {availableTools.map(
                (tool) => (
                  <span
                    className="agent-pill"
                    key={tool}
                  >
                    {tool}
                  </span>
                )
              )}
            </div>
          ) : (
            <EmptyPanel
              icon={Bot}
              message="No tools advertised by the API."
            />
          )}

          <div
            style={{
              marginTop: 30,
              paddingTop: 18,
              borderTop:
                '1px solid hsl(var(--border))',
            }}
          >
            <div className="panel-title">
              <h2>
                Traceability standard
              </h2>
            </div>

            <p
              className="muted"
              style={{
                fontSize: 12,
                lineHeight: 1.65,
                margin: 0,
              }}
            >
              Each run retains its
              thread, question, involved
              agents, timestamps, and
              structured result. Use this
              ledger as the operational
              handoff between analysis and
              review.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

function ActivityRow({
  run,
}: {
  run: AgentRun;
}) {
  const result = run.result as any;

  const risk = result?.risk;
  const policy = result?.policy;
  const audit = result?.audit;
  const evidence = result?.evidence ?? [];
  const agents = run.agents_involved ?? [];
  return (
    <div className="timeline-row">
      <div className="timeline-dot">
        {run.status?.toLowerCase() ===
        'completed' ? (
          <Check />
        ) : (
          <CircleDot />
        )}
      </div>

      <div className="timeline-content">
        <div className="timeline-top">
          <span className="primary-text">
            {run.current_agent ??
              run.agents_involved?.[0] ??
              'Agent workflow'}
          </span>

          <StatusChip
            value={run.status}
          />
        </div>

        <div
          style={{
            fontSize: 12,
            lineHeight: 1.45,
          }}
        >
          {run.question}
        </div>

        <div
          className="run-meta"
          style={{ marginTop: 10 }}
        >
          <span>
            {fmtDate(run.started_at)} ·{' '}
            {fmtTime(run.started_at)}
          </span>

          <span>·</span>

          <span>
            {run.agents_involved
              ?.length ?? 0}{' '}
            agents
          </span>

          {run.trace_url && (
            <a
              href={run.trace_url}
              target="_blank"
              rel="noreferrer"
              className="run-agent"
            >
              Open trace{' '}
              <ArrowUpRight size={10} />
            </a>
          )}
        </div>

        {run.error && (
          <div
            className="muted"
            style={{
              color:
                'hsl(var(--destructive))',
              fontSize: 11,
              marginTop: 9,
            }}
          >
            {run.error}
          </div>
        )}
        {run.result && (
  <div
    style={{
      marginTop: 18,
      paddingTop: 16,
      borderTop: '1px solid hsl(var(--border))',
    }}
  >
    {/* 1. AGENT WORKFLOW */}
    <div>
      <div className="panel-kicker" style={{ marginBottom: 10 }}>
        AGENT WORKFLOW
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 8,
          alignItems: 'center',
        }}
      >
        {agents.map((agent, index) => (
          <span key={agent} style={{ display: 'contents' }}>
            <span className="agent-pill">
              {agent}
            </span>

            {index < agents.length - 1 && (
              <span className="muted">→</span>
            )}
            </span>
        ))}
      </div>
    </div>

    {/* 2. DECISION SUMMARY */}
    <div style={{ marginTop: 18 }}>
      <div className="panel-kicker" style={{ marginBottom: 10 }}>
        DECISION SUMMARY
      </div>

      <div
        style={{
          display: 'flex',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <span className="agent-pill">
          Status: {policy?.compliance_status ?? 'N/A'}
        </span>

        <span className="agent-pill">
          Risk: {risk?.risk_level ?? 'N/A'}
        </span>

        <span className="agent-pill">
          Evidence: {evidence.length}
        </span>
      </div>
    </div>

    {/* 3. WHY THIS DECISION */}
    <div style={{ marginTop: 18 }}>
      <div className="panel-kicker" style={{ marginBottom: 10 }}>
        WHY THIS DECISION?
      </div>

      <p
        className="muted"
        style={{
          fontSize: 12,
          lineHeight: 1.6,
          margin: 0,
        }}
      >
        {audit?.audit_summary ??
          risk?.rationale ??
          'No decision rationale available.'}
      </p>
    </div>
    </div>
    )}
  </div>
  </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Router                                                                      */
/* -------------------------------------------------------------------------- */

function Router() {
  return (
    <Shell>
      <ErrorBoundary>
        <Switch>
          <Route
            path="/"
            component={Dashboard}
          />

          <Route
            path="/documents"
            component={Documents}
          />

          <Route
            path="/assistant"
            component={Assistant}
          />

          <Route
            path="/issues"
            component={Issues}
          />

          <Route
            path="/reports"
            component={Reports}
          />

          <Route
            path="/activity"
            component={Activity}
          />

          <Route
            component={NotFound}
          />
        </Switch>
      </ErrorBoundary>
    </Shell>
  );
}

/* -------------------------------------------------------------------------- */
/* App                                                                         */
/* -------------------------------------------------------------------------- */

export default function App() {
  return (
    <QueryClientProvider
      client={queryClient}
    >
      <Router />
    </QueryClientProvider>
  );
}