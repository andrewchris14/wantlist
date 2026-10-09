import {defineConfig} from '@playwright/test';import {existsSync} from 'node:fs';
// No web server, relay, database or external requests: all browser traffic mocked.
export default defineConfig({testDir:'./local-full-tests',workers:1,reporter:'list',timeout:60000,use:{viewport:{width:1440,height:1000},launchOptions:{executablePath:existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined,args:['--no-sandbox']},trace:'off',screenshot:'off'},outputDir:'../work/local-full-browser-results'});
