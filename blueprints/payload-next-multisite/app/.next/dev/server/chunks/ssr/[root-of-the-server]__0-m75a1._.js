module.exports = [
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
"[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "dynamic",
    ()=>dynamic,
    "generateMetadata",
    ()=>generateMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$TitleCard$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/content.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/present.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/site.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$metadata$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/seo/metadata.ts [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
const dynamic = 'force-dynamic';
const generateMetadata = async ()=>{
    const site = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["currentSite"])();
    // Поиск — функция для посетителя, а не посадочная страница: всегда noindex,
    // canonical не выставляется вовсе.
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$metadata$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMetadata"])({
        tenant: site.tenant,
        pageType: 'search',
        path: '/search/',
        heading: 'Поиск'
    }, site.siteName);
};
const SearchPage = async ({ searchParams })=>{
    const site = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["currentSite"])();
    const payload = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["payloadClient"])();
    const params = await searchParams;
    const query = typeof params.q === 'string' ? params.q : '';
    const results = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["searchSite"])(payload, site.tenant, query);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h1", {
                children: "Поиск"
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                lineNumber: 32,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                className: "row",
                action: "/search/",
                role: "search",
                style: {
                    marginBottom: '1.5rem'
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                        className: "visually-hidden",
                        htmlFor: "q",
                        children: "Поисковый запрос"
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                        lineNumber: 34,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                        id: "q",
                        name: "q",
                        type: "search",
                        defaultValue: query,
                        style: {
                            minHeight: 44,
                            padding: '0 0.75rem'
                        }
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                        lineNumber: 37,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "button",
                        type: "submit",
                        children: "Найти"
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                        lineNumber: 38,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                lineNumber: 33,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            query.trim() === '' ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "notice",
                children: "Введите запрос, чтобы найти материалы этого сайта."
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                lineNumber: 44,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Fragment"], {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                        className: "section",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                children: "Тайтлы"
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                                lineNumber: 48,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$TitleCard$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CardGrid"], {
                                items: results.titles.map(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantTitleCard"]),
                                empty: "Ничего не найдено."
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                                lineNumber: 49,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                        lineNumber: 47,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                        className: "section",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                children: "Материалы"
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                                lineNumber: 52,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0)),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$TitleCard$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CardGrid"], {
                                items: results.posts.map(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["postCard"]),
                                empty: "Ничего не найдено."
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                                lineNumber: 53,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                        lineNumber: 51,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
                lineNumber: 46,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx",
        lineNumber: 31,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = SearchPage;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx [app-rsc] (ecmascript, Next.js Server Component)", (function(__turbopack_context__){

__turbopack_context__.n(__turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/search/page.tsx [app-rsc] (ecmascript)"));
}),
"[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CardGrid",
    ()=>CardGrid,
    "TitleCard",
    ()=>TitleCard
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/app-dir/link.react-server.js [app-rsc] (ecmascript)");
;
;
const TitleCard = ({ item })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("article", {
        className: "card",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"], {
            href: item.href,
            children: [
                item.image?.url && item.image.alt ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                    className: "card__poster",
                    src: item.image.url,
                    alt: item.image.alt,
                    loading: "lazy"
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                    lineNumber: 15,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "card__poster",
                    "aria-hidden": "true"
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                    lineNumber: 17,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0)),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "card__body",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "card__title",
                            children: item.title
                        }, void 0, false, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                            lineNumber: 20,
                            columnNumber: 9
                        }, ("TURBOPACK compile-time value", void 0)),
                        item.meta ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "card__meta",
                            children: item.meta
                        }, void 0, false, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                            lineNumber: 21,
                            columnNumber: 22
                        }, ("TURBOPACK compile-time value", void 0)) : null
                    ]
                }, void 0, true, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                    lineNumber: 19,
                    columnNumber: 7
                }, ("TURBOPACK compile-time value", void 0))
            ]
        }, void 0, true, {
            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
            lineNumber: 13,
            columnNumber: 5
        }, ("TURBOPACK compile-time value", void 0))
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
        lineNumber: 12,
        columnNumber: 3
    }, ("TURBOPACK compile-time value", void 0));
const CardGrid = ({ items, empty })=>{
    if (items.length === 0) return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
        className: "notice",
        children: empty
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
        lineNumber: 28,
        columnNumber: 34
    }, ("TURBOPACK compile-time value", void 0));
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "grid",
        children: items.map((item)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(TitleCard, {
                item: item
            }, item.href, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
                lineNumber: 32,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)))
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/TitleCard.tsx",
        lineNumber: 30,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
}),
"[project]/blueprints/payload-next-multisite/app/src/lib/content.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PAGE_SIZE",
    ()=>PAGE_SIZE,
    "getCollection",
    ()=>getCollection,
    "getPage",
    ()=>getPage,
    "getPost",
    ()=>getPost,
    "getTenantTitle",
    ()=>getTenantTitle,
    "listCollections",
    ()=>listCollections,
    "listEpisodes",
    ()=>listEpisodes,
    "listGenres",
    ()=>listGenres,
    "listPosts",
    ()=>listPosts,
    "listReleaseEvents",
    ()=>listReleaseEvents,
    "listSeasons",
    ()=>listSeasons,
    "listTenantTitles",
    ()=>listTenantTitles,
    "searchSite",
    ()=>searchSite
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/tenant-query.ts [app-rsc] (ecmascript)");
;
const PAGE_SIZE = 24;
const publishedOnly = {
    _status: {
        equals: 'published'
    }
};
const listTenantTitles = async (payload, tenant, options = {})=>{
    const where = options.genreId ? {
        and: [
            publishedOnly,
            {
                'title.genres': {
                    in: [
                        options.genreId
                    ]
                }
            }
        ]
    } : publishedOnly;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
        collection: 'tenant-titles',
        tenant,
        where,
        page: options.page ?? 1,
        limit: options.limit ?? PAGE_SIZE,
        sort: options.sort ?? '-updatedAt',
        depth: 2
    });
};
const getTenantTitle = async (payload, tenant, slug)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(payload, {
        collection: 'tenant-titles',
        tenant,
        where: {
            and: [
                publishedOnly,
                {
                    slug: {
                        equals: slug
                    }
                }
            ]
        },
        depth: 2
    });
const listPosts = async (payload, tenant, options = {})=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
        collection: 'posts',
        tenant,
        where: publishedOnly,
        page: options.page ?? 1,
        limit: options.limit ?? 12,
        sort: '-publishedAt',
        depth: 1
    });
const getPost = async (payload, tenant, slug)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(payload, {
        collection: 'posts',
        tenant,
        where: {
            and: [
                publishedOnly,
                {
                    slug: {
                        equals: slug
                    }
                }
            ]
        },
        depth: 1
    });
const listCollections = async (payload, tenant, options = {})=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
        collection: 'editorial-collections',
        tenant,
        where: publishedOnly,
        page: options.page ?? 1,
        limit: options.limit ?? 12,
        depth: 2
    });
const getCollection = async (payload, tenant, slug)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(payload, {
        collection: 'editorial-collections',
        tenant,
        where: {
            and: [
                publishedOnly,
                {
                    slug: {
                        equals: slug
                    }
                }
            ]
        },
        depth: 2
    });
const getPage = async (payload, tenant, slug)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(payload, {
        collection: 'pages',
        tenant,
        where: {
            and: [
                publishedOnly,
                {
                    slug: {
                        equals: slug
                    }
                }
            ]
        },
        depth: 1
    });
const listGenres = async (payload)=>payload.find({
        collection: 'genres',
        limit: 100,
        sort: 'name',
        depth: 0,
        overrideAccess: true
    });
const listSeasons = async (payload, titleId)=>payload.find({
        collection: 'seasons',
        where: {
            title: {
                equals: titleId
            }
        },
        sort: 'number',
        limit: 100,
        depth: 0,
        overrideAccess: true
    });
const listEpisodes = async (payload, seasonId)=>payload.find({
        collection: 'episodes',
        where: {
            season: {
                equals: seasonId
            }
        },
        sort: 'number',
        limit: 500,
        depth: 0,
        overrideAccess: true
    });
const listReleaseEvents = async (payload, options)=>payload.find({
        collection: 'release-events',
        where: {
            and: [
                {
                    airsAt: {
                        greater_than_equal: options.from.toISOString()
                    }
                },
                {
                    airsAt: {
                        less_than: options.to.toISOString()
                    }
                }
            ]
        },
        sort: 'airsAt',
        limit: 200,
        depth: 1,
        overrideAccess: true
    });
const searchSite = async (payload, tenant, query)=>{
    const trimmed = query.trim().slice(0, 120);
    if (!trimmed) return {
        titles: [],
        posts: []
    };
    const [titles, posts] = await Promise.all([
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
            collection: 'tenant-titles',
            tenant,
            where: {
                and: [
                    publishedOnly,
                    {
                        'title.primaryName': {
                            like: trimmed
                        }
                    }
                ]
            },
            limit: 20,
            depth: 2
        }),
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
            collection: 'posts',
            tenant,
            where: {
                and: [
                    publishedOnly,
                    {
                        headline: {
                            like: trimmed
                        }
                    }
                ]
            },
            limit: 20,
            depth: 1
        })
    ]);
    return {
        titles: titles.docs,
        posts: posts.docs
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/src/lib/present.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "collectionCard",
    ()=>collectionCard,
    "describe",
    ()=>describe,
    "plainText",
    ()=>plainText,
    "postCard",
    ()=>postCard,
    "tenantTitleCard",
    ()=>tenantTitleCard,
    "titleNameOf",
    ()=>titleNameOf
]);
/**
 * Приведение документов к виду, который рендерит список. Ничего не выдумывает:
 * если названия или alt нет, поле остаётся пустым, а не заполняется заглушкой.
 */ const asRecord = (value)=>value && typeof value === 'object' ? value : null;
const titleNameOf = (tenantTitle)=>{
    const shared = asRecord(asRecord(tenantTitle)?.title);
    return String(shared?.primaryName ?? '').trim();
};
const imageOf = (source)=>{
    const media = asRecord(source);
    if (!media) return null;
    const sizes = asRecord(media.sizes);
    const card = asRecord(sizes?.card);
    const url = String(card?.url ?? media.url ?? '').trim();
    const alt = String(media.alt ?? '').trim();
    // Без alt изображение не показывается: пустой alt в публикации — дефект доступности.
    if (!url || !alt) return null;
    return {
        url,
        alt
    };
};
const tenantTitleCard = (doc)=>{
    const record = asRecord(doc) ?? {};
    const shared = asRecord(record.title);
    const year = shared?.year;
    const kind = shared?.kind;
    const kindLabel = kind === 'movie' ? 'фильм' : kind === 'ova' ? 'OVA/ONA' : 'сериал';
    return {
        href: `/catalog/${String(record.slug ?? '')}/`,
        title: titleNameOf(doc) || String(record.slug ?? ''),
        meta: [
            kindLabel,
            year ? String(year) : null
        ].filter(Boolean).join(' · '),
        image: imageOf(shared?.poster)
    };
};
const postCard = (doc)=>{
    const record = asRecord(doc) ?? {};
    const published = record.publishedAt ? new Date(String(record.publishedAt)) : null;
    return {
        href: `/news/${String(record.slug ?? '')}/`,
        title: String(record.headline ?? ''),
        meta: published ? published.toLocaleDateString('ru-RU') : null,
        image: imageOf(record.cover)
    };
};
const collectionCard = (doc)=>{
    const record = asRecord(doc) ?? {};
    const items = Array.isArray(record.items) ? record.items.length : 0;
    return {
        href: `/collections/${String(record.slug ?? '')}/`,
        title: String(record.name ?? ''),
        meta: items > 0 ? `${items} материалов` : null,
        image: imageOf(record.cover)
    };
};
const plainText = (value)=>String(value ?? '').replace(/\s+/g, ' ').trim();
const describe = (...candidates)=>{
    for (const candidate of candidates){
        const text = plainText(candidate);
        if (text.length >= 40) return text.slice(0, 300);
    }
    return null;
};
}),
"[project]/blueprints/payload-next-multisite/app/src/seo/metadata.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "absoluteUrl",
    ()=>absoluteUrl,
    "buildMetadata",
    ()=>buildMetadata,
    "hasNonIndexableParams",
    ()=>hasNonIndexableParams,
    "resolveSeo",
    ()=>resolveSeo
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$matrix$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/seo/matrix.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$profiles$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/seo/profiles.ts [app-rsc] (ecmascript)");
;
;
const origin = (tenant)=>`https://${tenant.domain}`;
const absoluteUrl = (tenant, path)=>{
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${origin(tenant)}${normalized}`;
};
const applyTemplate = (template, values)=>template.replace(/\{(\w+)\}/g, (_, key)=>values[key] ?? '');
const resolveSeo = (input, siteName)=>{
    const profile = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$profiles$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["profileFor"])(input.tenant.seoProfile);
    const rule = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$matrix$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PAGE_TYPES"][input.pageType];
    const reasons = [];
    let indexable = rule.index === 'index' || rule.index === 'conditional' || rule.index === 'inherit_from_parent';
    if (!indexable) reasons.push(`матрица: тип ${input.pageType} не индексируется`);
    if (indexable && !profile.indexable[input.pageType]) {
        indexable = false;
        reasons.push(`профиль ${profile.label}: тип ${input.pageType} закрыт на этом сайте`);
    }
    if (indexable && profile.requiresOwnText.includes(input.pageType) && !(input.ownText ?? '').trim()) {
        indexable = false;
        reasons.push(`профиль ${profile.label}: у страницы нет собственного текста сайта`);
    }
    if (indexable && input.documentRobots === 'noindex') {
        indexable = false;
        reasons.push('редакция закрыла страницу от индексации');
    }
    if (indexable && !input.tenant.indexingEnabled) {
        indexable = false;
        reasons.push('индексация сайта ещё не разрешена в настройках сайта');
    }
    const template = (input.page && input.page > 1 ? profile.titleTemplates.paginated_page : undefined) ?? profile.titleTemplates[input.pageType] ?? '{page} — {site}';
    const title = applyTemplate(template, {
        page: input.heading,
        site: siteName,
        n: String(input.page ?? 1)
    }).trim();
    const canonical = rule.canonical === 'none_no_index' || !indexable ? null : absoluteUrl(input.tenant, input.path);
    return {
        robots: indexable ? 'index,follow' : rule.follow ? 'noindex,follow' : 'noindex,nofollow',
        canonical,
        title,
        description: input.description?.trim() || null,
        indexable,
        reasons
    };
};
const buildMetadata = (input, siteName)=>{
    const seo = resolveSeo(input, siteName);
    const metadata = {
        title: seo.title,
        description: seo.description ?? undefined,
        robots: seo.robots,
        alternates: seo.canonical ? {
            canonical: seo.canonical
        } : undefined,
        openGraph: {
            type: 'website',
            title: seo.title,
            description: seo.description ?? undefined,
            url: seo.canonical ?? undefined,
            siteName,
            locale: 'ru_RU',
            images: input.image ? [
                {
                    url: input.image.url,
                    alt: input.image.alt
                }
            ] : undefined
        }
    };
    return metadata;
};
const hasNonIndexableParams = (search)=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$matrix$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["NON_INDEXABLE_PARAMS"].some((param)=>search.has(param));
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__0-m75a1._.js.map