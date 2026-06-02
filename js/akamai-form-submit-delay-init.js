// Patch screen/window dimensions to match a real macOS Firefox profile.
// Playwright sets a synthetic 1280×720 viewport where screen.width == outerWidth == innerWidth
// and devicePixelRatio == 1.  On real Mac Retina hardware, dpr=2 and screen dimensions
// reflect the physical display (not the viewport), which Akamai's sensor checks on page load.
// Values match a 14-inch MacBook (1440×900 logical resolution, Retina dpr=2):
//   availHeight = 900 - 37 (macOS Dock) = 863
//   outerWidth  = innerWidth  + 17 (scrollbar)
//   outerHeight = innerHeight + 92 (Firefox toolbar + tab bar)
// Akamai does not require an exact hardware match; any realistic Retina Mac profile passes.
// The detectable signal is the all-equal values Playwright produces by default — not the specific numbers.
(function() {
    Object.defineProperty(window, 'devicePixelRatio', {get: function() { return 2; }, configurable: true});
    Object.defineProperty(screen, 'width',       {get: function() { return 1440; }, configurable: true});
    Object.defineProperty(screen, 'height',      {get: function() { return 900; }, configurable: true});
    Object.defineProperty(screen, 'availWidth',  {get: function() { return 1440; }, configurable: true});
    Object.defineProperty(screen, 'availHeight', {get: function() { return 863; }, configurable: true});
    Object.defineProperty(window, 'outerWidth',  {get: function() { return window.innerWidth + 17; }, configurable: true});
    Object.defineProperty(window, 'outerHeight', {get: function() { return window.innerHeight + 92; }, configurable: true});
})();

// Hide automation flag at document_start.  Patch Navigator.prototype rather than the
// navigator instance so Object.getOwnPropertyDescriptor(navigator, 'webdriver') returns
// undefined — matching real Firefox where webdriver lives on the prototype, not the
// instance.  An own property on the instance is a detectable automation fingerprint.
(function() {
    var _wd = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    if (_wd && _wd.configurable) {
        Object.defineProperty(Navigator.prototype, 'webdriver', Object.assign({}, _wd, {get: function() { return false; }}));
    } else {
        Object.defineProperty(navigator, 'webdriver', {get: function() { return false; }, configurable: true, enumerable: true});
    }
})();

// Belt-and-suspenders: if GTM triggers native form submission (not location.href),
// this prevents immediate navigation and delays it 5 s so the Akamai sensor XHR
// can complete.  The primary timing mechanism is page.route() on the Python side.
(function() {
    var _origSubmit = HTMLFormElement.prototype.submit;
    var _submitting = false;
    function delayAndSubmit(form) {
        if (_submitting) return;
        _submitting = true;
        setTimeout(function() { _submitting = false; _origSubmit.call(form); }, 5000);
    }
    document.addEventListener('submit', function(e) {
        e.preventDefault();
        delayAndSubmit(e.target);
    }, false);
})();
