// Everything project-specific about the recordings. To reuse the kit in another
// project, copy tools/uat-video and change this file (and cases/common.js).
const path = require('path');

module.exports = {
  base: 'https://carejiox.com',
  // Title-card line "System"
  systemLabel: 'carejiox.com (live system), English, Vietnam time',
  timezone: 'Asia/Ho_Chi_Minh',
  tzLabel: 'Vietnam time',
  locale: 'en-US',
  geolocation: { latitude: 21.0136, longitude: 105.8487 },   // Hà Nội; the nurse app asks for it
  // Sign-in: login page, the URL a staff sign-in lands on, the URL the nurse app lands on
  loginPath: '/web/login',
  logoutPath: '/web/session/logout',
  landing: /\/bizapp/,
  pwaLanding: /health_pwa/,
  pwaLoginRedirect: '?redirect=%2Fhealth_pwa%3F%23%2Ftoday',
  // Server calls whose errors are printed to the console while recording
  rpcPath: '/web/dataset/call_kw',
  // White-label guard: this word must never be visible on screen
  brandWord: /odoo/i,
  // Where each test's folder (MP4, subtitles, proof stills, run.json) is written
  evidenceRoot: path.resolve(__dirname, '../../outputs/carejiox-uat-20261029/video-evidence'),
  // Second-language subtitle track (switchable, off by default)
  sub: { code: 'vie', title: 'Tiếng Việt', step: 'Bước', pass: 'Kết quả: ĐẠT', fail: 'Kết quả: KHÔNG ĐẠT', file: 'Vietnamese' },
};
