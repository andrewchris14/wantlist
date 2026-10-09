import {defineConfig} from '@playwright/test';
import {existsSync} from 'node:fs';
export default defineConfig({testDir:'./tests',workers:1,reporter:'list',timeout:90000,use:{viewport:{width:1100,height:900},launchOptions:{executablePath:existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined,args:['--no-sandbox']},trace:'off',screenshot:'off'},outputDir:'../../work/windows-backup-browser-results'});
