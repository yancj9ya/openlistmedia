(function () {
  const entryLink = document.getElementById('frontend-entry');
  const messageEl = document.getElementById('legacy-message');
  const configuredUrl = new URLSearchParams(window.location.search).get('frontend');
  const fallbackUrl = '/';
  const targetUrl = configuredUrl || fallbackUrl;

  if (entryLink) {
    entryLink.setAttribute('href', targetUrl);
  }

  if (messageEl) {
    messageEl.textContent = configuredUrl
      ? `检测到兼容跳转地址：${configuredUrl}`
      : '未指定新前端地址，默认跳转到当前站点根路径。';
  }
})();
