// GTM patches HTMLFormElement.prototype.submit during its own initialization
// (to intercept form events for conversion tracking), silently replacing the
// init-script delay with its own version.  Without this repatch the patched
// delay no longer exists when the login form is submitted: form.submit() fires
// immediately, the Akamai sensor XHR is aborted (NS_BINDING_ABORTED), and the
// server returns 403 because it received no fingerprint data.
// State is local — no window.* globals.
(() => {
    const _orig = HTMLFormElement.prototype.submit;
    let _busy = false;
    HTMLFormElement.prototype.submit = function() {
        if (_busy) return;
        _busy = true;
        const form = this; // explicit capture; safe against accidental conversion to regular function
        setTimeout(() => { _busy = false; _orig.call(form); }, 5000);
    };
})();
