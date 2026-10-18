export default async function({page}) { await page.reload({waitUntil:'domcontentloaded'}); return {reloaded:true,url:page.url()}; }
