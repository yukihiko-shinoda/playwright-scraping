// Patch screen/window dimensions to match a real macOS Firefox profile.
// Xvfb is started at 1440×900 so Firefox's viewport fills that display.  On real Mac Retina
// hardware, dpr=2 and screen dimensions reflect the physical display (not the viewport), which
// Akamai's sensor checks on page load.
// Values match a 14-inch MacBook (1440×900 logical resolution, Retina dpr=2):
//   availHeight = 900 - 37 (macOS Dock) = 863
//   outerWidth  = innerWidth  + 17 (scrollbar)
//   outerHeight = innerHeight + 92 (Firefox toolbar + tab bar)
// Akamai does not require an exact hardware match; any realistic Retina Mac profile passes.
// The detectable signal is mismatched values — e.g. screen.width ≠ actual viewport — not the specific numbers.
(function() {
    Object.defineProperty(window, 'devicePixelRatio', {get: function() { return 2; }, configurable: true});
    Object.defineProperty(screen, 'width',       {get: function() { return 1440; }, configurable: true});
    Object.defineProperty(screen, 'height',      {get: function() { return 900; }, configurable: true});
    Object.defineProperty(screen, 'availWidth',  {get: function() { return 1440; }, configurable: true});
    Object.defineProperty(screen, 'availHeight', {get: function() { return 863; }, configurable: true});
    Object.defineProperty(window, 'outerWidth',  {get: function() { return window.innerWidth + 17; }, configurable: true});
    Object.defineProperty(window, 'outerHeight', {get: function() { return window.innerHeight + 92; }, configurable: true});
})();

// Break canvas 2D fingerprint.  Linux (FreeType) and macOS (Core Text) render fonts to
// different pixel patterns; Akamai hashes the canvas output to fingerprint the OS.
// We force the bottom-right pixel's red-channel LSB to 1 inside every toDataURL call
// and restore it immediately.  The returned dataURL is a valid PNG with a consistent
// but non-Linux hash, while the live canvas is unchanged after the call.
(function() {
    var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {
        var ctx = this.getContext && this.getContext('2d');
        if (ctx && this.width >= 1 && this.height >= 1) {
            var x = this.width - 1, y = this.height - 1;
            var prev = ctx.getImageData(x, y, 1, 1);
            var mod = ctx.createImageData(1, 1);
            mod.data.set([prev.data[0] | 1, prev.data[1], prev.data[2], prev.data[3]]);
            ctx.putImageData(mod, x, y);
            var result = origToDataURL.apply(this, arguments);
            ctx.putImageData(prev, x, y);
            return result;
        }
        return origToDataURL.apply(this, arguments);
    };
})();

// Break AudioContext fingerprint.  Floating-point DSP processing produces different
// values on different CPU/OS combinations.  Adding a tiny fixed offset to the last
// sample of every AnalyserNode getFloatFrequencyData/getByteFrequencyData call produces
// a consistent but non-native hash.
(function() {
    if (typeof OfflineAudioContext === 'undefined') return;
    var origStartRendering = OfflineAudioContext.prototype.startRendering;
    OfflineAudioContext.prototype.startRendering = function() {
        return origStartRendering.call(this).then(function(buffer) {
            for (var ch = 0; ch < buffer.numberOfChannels; ch++) {
                var data = buffer.getChannelData(ch);
                if (data.length > 0) data[data.length - 1] += 1.2e-7;
            }
            return buffer;
        });
    };
})();

// Spoof WebGL renderer strings.  On Linux with no real GPU, getParameter() returns
// "Mesa" / "llvmpipe" — a hard bot signal.  Patch both WebGL1 and WebGL2 contexts
// to return values matching Apple Silicon Mac hardware.
(function() {
    var UNMASKED_VENDOR   = 0x9245;
    var UNMASKED_RENDERER = 0x9246;
    function patchGL(proto) {
        var orig = proto.getParameter;
        proto.getParameter = function(pname) {
            if (pname === UNMASKED_VENDOR)   return 'Apple';
            if (pname === UNMASKED_RENDERER) return 'Apple GPU';
            return orig.call(this, pname);
        };
    }
    if (typeof WebGLRenderingContext  !== 'undefined') patchGL(WebGLRenderingContext.prototype);
    if (typeof WebGL2RenderingContext !== 'undefined') patchGL(WebGL2RenderingContext.prototype);
})();

// Spoof several Gecko-only Navigator properties that directly expose Linux even when
// the context userAgent is overridden to macOS.  Firefox derives oscpu, appVersion,
// and buildID from the compiled binary, not from the overridden userAgent string.
(function() {
    var FF_MAJOR = navigator.userAgent.match(/Firefox\/(\d+)/);
    FF_MAJOR = FF_MAJOR ? FF_MAJOR[1] : '150';
    var MAC_OS = 'Intel Mac OS X 10.15';
    var defs = {
        // oscpu: Gecko-only; maps directly to the compiled OS string ("Linux x86_64" on Linux).
        oscpu:      {get: function() { return MAC_OS; }},
        // platform: "Linux x86_64" / "Linux aarch64" on Linux vs "MacIntel" on macOS.
        platform:   {get: function() { return 'MacIntel'; }},
        // appVersion: Firefox ignores context.userAgent for this property; still returns
        //   "5.0 (X11)" on Linux.  Must match the overridden userAgent minus "Mozilla/".
        appVersion: {get: function() { return '5.0 (Macintosh; ' + MAC_OS + '; rv:' + FF_MAJOR + '.0) Gecko/20100101 Firefox/' + FF_MAJOR + '.0'; }},
        // buildID: Playwright sets a fake "20181001000000"; real Firefox has a real timestamp.
        buildID:    {get: function() { return '20241015135139'; }},
    };
    for (var prop in defs) {
        (function(p, getter) {
            try {
                // Build a clean accessor descriptor — never merge with an existing data descriptor
                // (Object.assign of {value, writable} + {get} produces an invalid mixed descriptor
                // and throws TypeError, aborting the rest of the loop and killing the sensor script).
                var newDesc = {get: getter, configurable: true, enumerable: true};
                var desc = Object.getOwnPropertyDescriptor(Navigator.prototype, p);
                if (desc && desc.configurable) {
                    Object.defineProperty(Navigator.prototype, p, newDesc);
                } else {
                    Object.defineProperty(navigator, p, newDesc);
                }
            } catch (e) {}
        })(prop, defs[prop].get);
    }
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
