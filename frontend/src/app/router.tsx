import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AppLayout } from './layout';
import { useAuth } from './providers';
import { CategoriesPage } from '../pages/categories-page';
import { MediaListPage } from '../pages/media-list-page';
import { MediaDetailPage } from '../pages/media-detail-page';
import { NotFoundPage } from '../pages/not-found-page';
import { SettingsPage } from '../pages/settings-page';
import { AccessGatePage } from '../pages/access-gate-page';

function RequireAuth() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

function RequireAdmin() {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  if (!isAdmin) {
    return <Navigate to="/media" replace />;
  }
  return <Outlet />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<AccessGatePage />} />
          <Route element={<RequireAuth />}>
            <Route path="/categories" element={<CategoriesPage />} />
            <Route path="/media" element={<MediaListPage />} />
            <Route path="/media/:mediaId" element={<MediaDetailPage />} />
          </Route>
          <Route element={<RequireAdmin />}>
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
