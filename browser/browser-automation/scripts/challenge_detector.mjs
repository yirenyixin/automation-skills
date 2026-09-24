import { readFileSync } from 'node:fs';

const path = process.argv[2];
if (!path) { console.error('Use: node challenge_detector.mjs <saved-dom.html>'); process.exit(1); }
const html = readFileSync(path, 'utf8').toLowerCase();
const signatures = [
  ['recaptcha', /g-recaptcha|iframe[^>]+recaptcha|recaptcha[^<]{0,160}(iframe|challenge)/],
  ['hcaptcha', /h-captcha|iframe[^>]+hcaptcha/], ['turnstile', /cf-turnstile|iframe[^>]+challenges\.cloudflare\.com/],
  ['captcha', /<(input|iframe)[^>]+(captcha|security[-_ ]?check|verification[-_ ]?code)/],
  ['slider', /(slider[-_ ]?(captcha|verify|challenge)|drag[-_ ]?(captcha|verify)|geetest|nc_1_n1z)/],
  ['otp', /<input[^>]+(otp|one[-_ ]?time|verification[-_ ]?code|authenticator)/]
];
const detected = signatures.filter(([, pattern]) => pattern.test(html)).map(([kind]) => kind);
console.log(JSON.stringify({ detected: detected.length > 0, kinds: detected, action: detected.length ? 'pause_for_user' : 'continue' }, null, 2));

