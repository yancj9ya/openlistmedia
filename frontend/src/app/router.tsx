import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AppLayout } from './layout';
import { useAuth } from './providers';
import { AsyncState } from '../shared/ui/async-state';

const CategoriesPage = lazy(() =>
  import('../pages/categories-page').then((m) => ({ default: m.CategoriesPage })),
);
const MediaListPage = lazy(() =>
  import('../pages/media-list-page').then((m) => ({ default: m.MediaListPage })),
);
const MediaDetailPage = lazy(() =>
  import('../pages/media-detail-page').then((m) => ({ default: m.MediaDetailPage })),
);
const NotFoundPage = lazy(() =>
  import('../pages/not-found-page').then((m) => ({ default: m.NotFoundPage })),
);
const SettingsPage = lazy(() =>
  import('../pages/settings-page').then((m) => ({ default: m.SettingsPage })),
);
const AccessGatePage = lazy(() =>
  import('../pages/access-gate-page').then((m) => ({ default: m.AccessGatePage })),
);

function PageFallback() {
  return (
    <AsyncState loading>
      <></>
    </AsyncState>
  );
}

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
      <Suspense fallback={<PageFallback />}>
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
      </Suspense>
    </BrowserRouter>
  );
}
