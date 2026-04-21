import { Outlet } from 'react-router-dom';

export function AppLayout() {
  return (
    <div className="app-shell">
      <main className="page-container">
        <Outlet />
      </main>
    </div>
  );
}