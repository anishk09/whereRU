import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({ plugins:[{name:"local-lato-fonts",enforce:"pre",transform(code,id){
if(id.split("?")[0].endsWith("/src/index.css"))return code.replaceAll("./public/fonts/","/fonts/").replace(/^@import url\("https:\/\/fonts\.googleapis\.com[^\n]+\n/m,"");
}},react(),tailwindcss()], server:{host:'0.0.0.0',port:8444,strictPort:true,proxy:{'/api':'http://127.0.0.1:5003'}}, preview:{host:'0.0.0.0',port:8444,proxy:{'/api':'http://127.0.0.1:5003'}}, build:{chunkSizeWarningLimit:1500} });
