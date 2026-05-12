import React, { useEffect, useMemo, useState } from 'react';
import { ArrowUp, FolderOpen, FileText, RefreshCw, HardDrive, ChevronRight } from 'lucide-react';

function formatSize(bytes) {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes / 1024;
  let unit = units[0];
  for (let i = 0; i < units.length; i += 1) {
    unit = units[i];
    if (size < 1024 || i === units.length - 1) break;
    size /= 1024;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${unit}`;
}

function normalizePath(path) {
  if (!path || path === '.' || path === '/') return '';
  return path.replace(/^\/+/, '').replace(/\\/g, '/');
}

export default function FilesystemExplorer({ api, token }) {
  const [currentPath, setCurrentPath] = useState('');
  const [entries, setEntries] = useState([]);
  const [selected, setSelected] = useState(null);
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const breadcrumbs = useMemo(() => {
    const parts = normalizePath(currentPath).split('/').filter(Boolean);
    const crumbs = [{ label: 'ROOT', path: '' }];
    let running = '';
    parts.forEach((part) => {
      running = running ? `${running}/${part}` : part;
      crumbs.push({ label: part, path: running });
    });
    return crumbs;
  }, [currentPath]);

  const fetchDirectory = async (nextPath = '') => {
    setLoading(true);
    setError('');
    try {
      const query = nextPath ? `?path=${encodeURIComponent(nextPath)}` : '';
      const resp = await fetch(`${api}/api/os/fs/list${query}`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || 'Unable to read directory');
      setEntries(data.entries || []);
      setCurrentPath(data.path === '.' ? '' : data.path || nextPath);
      if (data.path !== selected?.parentPath) {
        setSelected(null);
        setPreview('');
      }
    } catch (err) {
      setError(err.message);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDirectory('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openEntry = async (entry) => {
    if (entry.type === 'directory') {
      const nextPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      await fetchDirectory(nextPath);
      return;
    }

    setBusy(true);
    setSelected({ ...entry, parentPath: currentPath });
    try {
      const targetPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      const resp = await fetch(`${api}/api/os/fs/read?path=${encodeURIComponent(targetPath)}`, {
        headers: { 'X-JARVIS-TOKEN': token, 'Content-Type': 'application/json' },
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || 'Unable to preview file');
      setPreview(data.content || '');
    } catch (err) {
      setPreview(err.message);
    } finally {
      setBusy(false);
    }
  };

  const goUp = async () => {
    if (!currentPath) return;
    const parts = currentPath.split('/').filter(Boolean);
    parts.pop();
    await fetchDirectory(parts.join('/'));
  };

  return (
    <div className="flex h-full flex-col overflow-hidden" data-testid="filesystem-panel">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-cyan-900/30">
        <HardDrive size={14} className="text-cyan-400" />
        <span className="font-display text-[9px] tracking-widest text-cyan-300/50 uppercase">Filesystem Navigator</span>
        <button
          onClick={() => fetchDirectory(currentPath)}
          className="ml-auto flex items-center gap-1 px-2 py-1 border border-cyan-900/40 text-cyan-300/60 text-[9px] uppercase tracking-widest hover:border-cyan-500/60 hover:text-cyan-300 transition-all"
          data-testid="fs-refresh-btn"
        >
          <RefreshCw size={11} /> Refresh
        </button>
      </div>

      <div className="px-4 py-2 border-b border-cyan-900/20 flex items-center gap-2 text-[9px] font-mono text-cyan-300/50 overflow-x-auto">
        <button onClick={() => fetchDirectory('')} className="hover:text-cyan-300 uppercase tracking-widest">
          ROOT
        </button>
        {breadcrumbs.slice(1).map((crumb) => (
          <React.Fragment key={crumb.path}>
            <ChevronRight size={10} className="text-cyan-900/60" />
            <button onClick={() => fetchDirectory(crumb.path)} className="hover:text-cyan-300 capitalize">
              {crumb.label}
            </button>
          </React.Fragment>
        ))}
      </div>

      <div className="grid flex-1 grid-cols-12 overflow-hidden">
        <div className="col-span-5 border-r border-cyan-900/20 overflow-y-auto">
          <div className="px-4 py-2 border-b border-cyan-900/20 flex items-center justify-between text-[9px] font-mono text-cyan-300/40 uppercase tracking-widest">
            <span>Location</span>
            <span>{normalizePath(currentPath) || 'root'}</span>
          </div>

          {loading && (
            <div className="p-4 text-cyan-400/60 font-mono text-xs">Scanning workspace...</div>
          )}
          {error && (
            <div className="p-4 text-red-400 font-mono text-xs">{error}</div>
          )}
          {!loading && !error && entries.length === 0 && (
            <div className="p-4 text-cyan-300/30 font-mono text-xs">No entries found.</div>
          )}

          <div className="divide-y divide-cyan-900/10">
            {entries.map((entry) => (
              <button
                key={`${entry.name}-${entry.type}`}
                onClick={() => openEntry(entry)}
                className={`w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-cyan-950/30 transition-colors ${
                  selected?.name === entry.name ? 'bg-cyan-950/40' : ''
                }`}
                data-testid={`fs-entry-${entry.name}`}
              >
                {entry.type === 'directory' ? (
                  <FolderOpen size={14} className="text-cyan-400 flex-shrink-0" />
                ) : (
                  <FileText size={14} className="text-cyan-300/70 flex-shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[11px] text-cyan-100">{entry.name}</span>
                    <span className="font-mono text-[9px] text-cyan-300/30 uppercase">{entry.type}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[9px] font-mono text-cyan-300/40">
                    <span>{formatSize(entry.size)}</span>
                    <span>{entry.modified || ''}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="col-span-7 flex flex-col overflow-hidden">
          <div className="px-4 py-2 border-b border-cyan-900/20 flex items-center gap-2">
            <button
              onClick={goUp}
              disabled={!currentPath}
              className="flex items-center gap-1 px-2 py-1 border border-cyan-900/40 text-cyan-300/60 text-[9px] uppercase tracking-widest disabled:opacity-30 hover:border-cyan-500/60 hover:text-cyan-300 transition-all"
              data-testid="fs-up-btn"
            >
              <ArrowUp size={11} /> Up
            </button>
            <span className="font-display text-[9px] tracking-widest text-cyan-300/40 uppercase">Preview</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed text-cyan-100/90">
            {selected ? (
              <>
                <div className="mb-3 text-[9px] uppercase tracking-widest text-cyan-300/40">
                  {selected.name} • {selected.type} • {formatSize(selected.size)}
                </div>
                {busy && <div className="text-cyan-400/60">Loading preview...</div>}
                <pre className="whitespace-pre-wrap break-words">{preview || 'No preview available.'}</pre>
              </>
            ) : (
              <div className="text-cyan-300/30 text-center mt-16">
                <HardDrive size={36} className="mx-auto mb-3 text-cyan-900/40" />
                <p>Select a file to preview it.</p>
                <p className="text-[10px] mt-1">Navigate the workspace like a system shell.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
