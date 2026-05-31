// Re-apply the form-submit delay patch AFTER all page scripts (GTM, Akamai) have
// loaded.  The init-script version is overwritten by GTM during its own init, so
// we must re-patch here to ensure our version is the last one active.
// Capturing _orig here chains onto whatever GTM left on the prototype so GTM's
// sensor logic still fires — navigation is just delayed 5 s to let it complete.
(() => {
    const _orig = HTMLFormElement.prototype.submit;
    let _busy = false;
    HTMLFormElement.prototype.submit = function() {
        if (!this.action || !this.action.includes('V0100')) {
            _orig.call(this);
            return;
        }
        if (_busy) return;
        _busy = true;
        setTimeout(() => { _busy = false; _orig.call(this); }, 5000);
    };
})();
