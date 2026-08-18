// Conditionally load the Telegram Mini App SDK.
// Plain website visitors never trigger a request to telegram.org.
// Inside a Telegram context the SDK is injected and a "tg-sdk-ready"
// event is dispatched so app.js can (re)initialise Telegram auth.
(function () {
  'use strict';

  function inTelegramContext() {
    try {
      var hash = window.location.hash || '';
      var search = window.location.search || '';
      if (hash.indexOf('tgWebAppData') !== -1 || search.indexOf('tgWebAppData') !== -1) {
        return true;
      }
      if (window.TelegramWebviewProxy || window.TelegramWebviewProxyProto) {
        return true;
      }
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        return true;
      }
      if (window.self !== window.top) {
        var ref = document.referrer || '';
        if (/https?:\/\/([^/]*\.)?(telegram\.org|telegram\.me|t\.me)/i.test(ref)) {
          return true;
        }
      }
    } catch (err) {
      // Cross-origin access (window.top) can throw when framed by Telegram.
      return true;
    }
    return false;
  }

  if (!inTelegramContext()) {
    return;
  }

  var script = document.createElement('script');
  script.src = 'https://telegram.org/js/telegram-web-app.js';
  script.async = false;
  script.onload = function () {
    try {
      window.dispatchEvent(new Event('tg-sdk-ready'));
    } catch (err) {
      /* no-op */
    }
  };
  (document.head || document.documentElement).appendChild(script);
})();
