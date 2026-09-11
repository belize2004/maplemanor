const fs = require("fs");
const path = require("path");

const srcHtmlPath = path.join(__dirname, "index.html");
const distDir = path.join(__dirname, "dist");
const deployDir = path.join(__dirname, "deploy_site");

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}
if (!fs.existsSync(deployDir)) {
  fs.mkdirSync(deployDir, { recursive: true });
}

fs.copyFileSync(srcHtmlPath, path.join(deployDir, "index.html"));
const htmlContent = fs.readFileSync(srcHtmlPath, "utf8");

const workerJs = `
const HTML_CONTENT = ${JSON.stringify(htmlContent)};
let MEMORY_COMMENTS = [];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type"
        }
      });
    }

    if (url.pathname === "/api/sync-comments" && request.method === "POST") {
      try {
        const data = await request.json();
        if (data && Array.isArray(data.comments)) {
          MEMORY_COMMENTS = data.comments;
          if (env.COMMENTS_KV) {
            await env.COMMENTS_KV.put("maplemanor_comments", JSON.stringify(data.comments));
          }
        }
        return new Response(JSON.stringify({ success: true, count: MEMORY_COMMENTS.length }), {
          headers: { 
            "Content-Type": "application/json", 
            "Access-Control-Allow-Origin": "*" 
          }
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { 
          status: 400, 
          headers: { 
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          } 
        });
      }
    }

    if (url.pathname === "/api/get-comments" && request.method === "GET") {
      if (env.COMMENTS_KV) {
        const stored = await env.COMMENTS_KV.get("maplemanor_comments");
        if (stored) {
          return new Response(JSON.stringify({ comments: JSON.parse(stored) }), {
            headers: { 
              "Content-Type": "application/json", 
              "Access-Control-Allow-Origin": "*" 
            }
          });
        }
      }
      return new Response(JSON.stringify({ comments: MEMORY_COMMENTS }), {
        headers: { 
          "Content-Type": "application/json", 
          "Access-Control-Allow-Origin": "*" 
        }
      });
    }

    return new Response(HTML_CONTENT, {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-cache, no-store, must-revalidate"
      }
    });
  }
};
`;

fs.writeFileSync(path.join(distDir, "worker.js"), workerJs, "utf8");
console.log("✓ Successfully generated dist/worker.js and deploy_site/index.html");
