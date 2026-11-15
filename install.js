/* 홈 화면 설치 안내: 같은 기기에서 한 번 거절하거나 설치하면 다시 띄우지 않는다 */
(function () {
  var KEY = "budgetA2HSDone";
  function seen() { try { return !!localStorage.getItem(KEY); } catch (e) { return false; } }
  function remember() { try { localStorage.setItem(KEY, "1"); } catch (e) { /* 저장 불가 환경은 무시 */ } }
  if (seen()) return;
  var standalone = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true;
  if (standalone) return;

  if ("serviceWorker" in navigator) { navigator.serviceWorker.register("sw.js").catch(function () {}); }

  var ua = navigator.userAgent || "";
  var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var isTelegram = /Telegram/i.test(ua);
  var isIOSSafari = isIOS && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS|KAKAOTALK|Line|FBAN|FBAV|Instagram/i.test(ua);

  var css = "#a2hs{position:fixed;left:8px;right:8px;bottom:calc(env(safe-area-inset-bottom) + 10px);z-index:90;background:#161a22;color:#f4f6fa;border:1px solid #2a3140;border-radius:14px;padding:12px 14px;font:14px/1.5 system-ui,-apple-system,'Malgun Gothic',sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.35)}" +
    "#a2hs p{margin:0 0 10px}" +
    ".a2hs-btns{display:flex;gap:8px;justify-content:flex-end}" +
    ".a2hs-btns button{border:1px solid #3a4456;background:transparent;color:#f4f6fa;border-radius:999px;padding:7px 14px;font:inherit;font-weight:700;cursor:pointer}" +
    ".a2hs-btns button.pri{background:#34d399;border-color:#34d399;color:#04241a}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  var box = null;
  function close() { if (box) { box.remove(); box = null; } remember(); }
  function card(msg, actions) {
    if (box) box.remove();
    box = document.createElement("div"); box.id = "a2hs"; box.setAttribute("role", "dialog");
    if (document.querySelector(".bar")) box.style.bottom = "calc(env(safe-area-inset-bottom) + 84px)";   // 지도 보기는 하단 메뉴 위에 띄운다
    box.innerHTML = "<p></p><div class='a2hs-btns'></div>";
    box.querySelector("p").textContent = msg;
    actions.forEach(function (a) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = a.label;
      if (a.primary) b.className = "pri";
      b.onclick = a.fn; box.querySelector(".a2hs-btns").appendChild(b);
    });
    document.body.appendChild(box);
  }

  if (isTelegram) {
    setTimeout(function () { card("텔레그램 안에서는 홈 화면에 설치할 수 없어요. 사파리나 크롬에서 열어 주세요.", [{ label: "확인", fn: close, primary: true }]); }, 1500);
    return;
  }
  if (isIOS) {
    if (!isIOSSafari) return;   // 아이폰의 다른 브라우저는 설치 메뉴가 없어 안내하지 않는다
    setTimeout(function () { card("홈 화면에 추가하면 앱처럼 바로 열 수 있어요. 하단 공유 버튼(□↑)을 누르고 '홈 화면에 추가'를 선택하세요.", [{ label: "확인", fn: close, primary: true }]); }, 1500);
    return;
  }

  var deferred = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferred = e;
    setTimeout(function () {
      if (!deferred || seen()) return;
      card("홈 화면에 설치하면 앱처럼 바로 열 수 있어요.", [
        { label: "나중에", fn: close },
        { label: "설치", primary: true, fn: function () {
          var p = deferred; deferred = null;
          p.prompt();
          p.userChoice.then(function () { close(); }, function () { close(); });
        } }
      ]);
    }, 1500);
  });
  window.addEventListener("appinstalled", remember);
})();
