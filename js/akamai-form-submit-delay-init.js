// Delay login form submission so Akamai's sensor POST can complete before the page
// navigates away.  Without this, Firefox aborts the sensor XHR (NS_BINDING_ABORTED)
// the moment navigation starts, and Akamai blocks the target page because no
// fingerprint data was received.
//
// Root cause: GTM (Google Tag Manager) intercepts the submit event in CAPTURE phase,
// fires sensors asynchronously, then calls form.submit() programmatically.
// form.submit() bypasses the submit event entirely, so a bubble-phase
// document.addEventListener('submit') can't prevent it.
//
// Fix: patch BOTH code paths:
//   1. HTMLFormElement.prototype.submit — catches programmatic form.submit()
//   2. document.addEventListener('submit') — catches native button-click submit
// A _submitting flag prevents double-firing when both paths trigger together.
// After a 5 s delay the sensor has time to complete and set its cookie.
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
(function() {
    var _origSubmit = HTMLFormElement.prototype.submit;
    var _submitting = false;

    function delayAndSubmit(form) {
        if (_submitting) return;
        _submitting = true;
        setTimeout(function() {
            _submitting = false;
            _origSubmit.call(form);
        }, 5000);
    }

    HTMLFormElement.prototype.submit = function() {
        if (!this.action || this.action.indexOf('V0100') === -1) {
            _origSubmit.call(this);
            return;
        }
        delayAndSubmit(this);
    };

    document.addEventListener('submit', function(e) {
        var form = e.target;
        if (!form || !form.action || form.action.indexOf('V0100') === -1) return;
        e.preventDefault();
        delayAndSubmit(form);
    }, false);
})();
