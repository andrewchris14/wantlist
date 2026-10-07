import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({root:'owner',plugins:[react()],build:{outDir:'../foundation/.local/editor-dist',emptyOutDir:true},server:{host:'0.0.0.0',port:5174,strictPort:true}});
