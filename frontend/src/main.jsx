import React from 'react';
import { createRoot } from 'react-dom/client';
import { Brain, CheckCircle2, FileText, Loader2, MessageSquareText, Play, Send, UploadCloud } from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api';

function App() {
  const [roles, setRoles] = React.useState([]);
  const [role, setRole] = React.useState('');
  const [resume, setResume] = React.useState(null);
  const [session, setSession] = React.useState(null);
  const [answer, setAnswer] = React.useState('');
  const [history, setHistory] = React.useState([]);
  const [summary, setSummary] = React.useState(null);
  const [health, setHealth] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    async function loadBootData() {
      try {
        const [rolesRes, healthRes] = await Promise.all([
          fetch(`${API_BASE}/roles`),
          fetch(`${API_BASE}/health`),
        ]);
        const loadedRoles = await rolesRes.json();
        const loadedHealth = await healthRes.json();
        setRoles(loadedRoles);
        setRole(loadedRoles[0]?.id || '');
        setHealth(loadedHealth);
      } catch {
        setError('Backend is not reachable. Start FastAPI on port 8000.');
      }
    }
    loadBootData();
  }, []);

  async function startInterview(event) {
    event.preventDefault();
    if (!resume || !role) {
      setError('Choose a role and upload a PDF or text resume.');
      return;
    }
    setLoading(true);
    setError('');
    setSummary(null);
    setHistory([]);
    try {
      const body = new FormData();
      body.append('role', role);
      body.append('resume', resume);
      const res = await fetch(`${API_BASE}/sessions`, { method: 'POST', body });
      if (!res.ok) throw new Error((await res.json()).detail || 'Could not start interview.');
      const data = await res.json();
      setSession(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer(event) {
    event.preventDefault();
    if (!answer.trim() || !session?.current_question) return;
    setLoading(true);
    setError('');
    const answeredQuestion = session.current_question;
    try {
      const res = await fetch(`${API_BASE}/sessions/${session.session_id}/answers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Could not submit answer.');
      const data = await res.json();
      setHistory((items) => [
        ...items,
        { question: answeredQuestion, answer, score: data.answer_score },
      ]);
      setAnswer('');
      if (data.status === 'completed') {
        setSummary(data.summary);
        setSession((current) => ({ ...current, status: 'completed', current_question: null }));
      } else {
        setSession((current) => ({ ...current, status: data.status, current_question: data.next_question }));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const selectedRole = roles.find((item) => item.id === role);

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="sidebar">
          <div className="brand-lockup">
            <span className="brand-mark"><Brain size={22} /></span>
            <div>
              <h1>Candidate Screening RAG</h1>
              <p>Role-aware interview system</p>
            </div>
          </div>

          <form className="start-form" onSubmit={startInterview}>
            <label>
              <span>Target role</span>
              <select value={role} onChange={(event) => setRole(event.target.value)}>
                {roles.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>

            <label className="upload-zone">
              <UploadCloud size={22} />
              <span>{resume ? resume.name : 'Upload resume PDF or text'}</span>
              <input
                type="file"
                accept=".pdf,.txt,text/plain,application/pdf"
                onChange={(event) => setResume(event.target.files?.[0] || null)}
              />
            </label>

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              Start Interview
            </button>
          </form>

          <div className="system-readout">
            <span className="readout-label">Knowledge chunks</span>
            <strong>{health?.knowledge_chunks ?? '...'}</strong>
          </div>

          {selectedRole && (
            <div className="role-note">
              <strong>{selectedRole.label}</strong>
              <p>{selectedRole.description}</p>
            </div>
          )}
        </aside>

        <section className="interview-panel">
          {error && <div className="error-banner">{error}</div>}

          {!session && (
            <div className="empty-state">
              <FileText size={36} />
              <h2>Upload a resume to begin</h2>
              <p>The backend will parse candidate signals, retrieve role-specific context, and generate the first grounded question.</p>
            </div>
          )}

          {session && (
            <>
              <div className="candidate-strip">
                <div>
                  <span>Candidate</span>
                  <strong>{session.candidate_name || 'Detected from resume'}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{session.status}</strong>
                </div>
                <div>
                  <span>Domains</span>
                  <strong>{session.domains.length ? session.domains.join(', ') : 'inferred during interview'}</strong>
                </div>
              </div>

              <div className="chips">
                {session.extracted_skills.map((skill) => <span key={skill}>{skill}</span>)}
                {!session.extracted_skills.length && <span>No explicit skills detected</span>}
              </div>

              <div className="timeline">
                {history.map((item, index) => (
                  <article className="turn" key={`${item.question.turn_number}-${index}`}>
                    <header>
                      <span><CheckCircle2 size={16} /> Question {item.question.turn_number}</span>
                      <strong>{item.score.score}%</strong>
                    </header>
                    <p>{item.question.question}</p>
                    <blockquote>{item.answer}</blockquote>
                    <small>{item.score.feedback}</small>
                  </article>
                ))}
              </div>

              {session.current_question && (
                <article className="active-question">
                  <header>
                    <span><MessageSquareText size={18} /> Question {session.current_question.turn_number}</span>
                    <strong>{session.current_question.difficulty}</strong>
                  </header>
                  <h2>{session.current_question.question}</h2>
                  <div className="trace-grid">
                    {session.current_question.retrieved_context.slice(0, 3).map((ctx) => (
                      <div key={ctx.chunk_id}>
                        <span>{ctx.source_title}</span>
                        <strong>{Math.round(ctx.score * 100)}%</strong>
                      </div>
                    ))}
                  </div>
                  <form onSubmit={submitAnswer} className="answer-form">
                    <textarea
                      value={answer}
                      onChange={(event) => setAnswer(event.target.value)}
                      placeholder="Write the candidate answer here..."
                      rows={7}
                    />
                    <button className="primary-button" type="submit" disabled={loading || !answer.trim()}>
                      {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
                      Submit Answer
                    </button>
                  </form>
                </article>
              )}

              {summary && (
                <section className="summary-band">
                  <div>
                    <span>Overall score</span>
                    <strong>{summary.overall_score}%</strong>
                  </div>
                  <div>
                    <span>Readiness</span>
                    <strong>{summary.readiness_band}</strong>
                  </div>
                  <p>{summary.recommendation}</p>
                  <div className="summary-lists">
                    <SummaryList title="Strengths" items={summary.strengths} />
                    <SummaryList title="Gaps" items={summary.gaps} />
                  </div>
                </section>
              )}
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function SummaryList({ title, items }) {
  return (
    <div>
      <h3>{title}</h3>
      {(items?.length ? items : ['No strong signal yet']).map((item) => <span key={item}>{item}</span>)}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
