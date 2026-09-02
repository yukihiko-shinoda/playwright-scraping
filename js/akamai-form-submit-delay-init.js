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
