// Hide the webdriver property so Akamai/bot-detection scripts do not flag this
// session as automated.  Also wraps navigator.credentials.create to log WebAuthn
// virtual-authenticator calls for debugging.
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
if (typeof PublicKeyCredential !== 'undefined') {
    const _orig = navigator.credentials.create.bind(navigator.credentials);
    navigator.credentials.create = async function(opts) {
        console.log('[PASSKEY] create called, rp:', opts?.publicKey?.rp?.id);
        try {
            const r = await _orig(opts);
            console.log('[PASSKEY] create OK, id prefix:', r?.id?.substring(0, 12));
            return r;
        } catch (e) {
            console.log('[PASSKEY] create ERROR:', e.name, ':', e.message);
            throw e;
        }
    };
}
