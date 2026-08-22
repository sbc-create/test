module.exports = [
"[externals]/next/dist/shared/lib/no-fallback-error.external.js [external] (next/dist/shared/lib/no-fallback-error.external.js, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("next/dist/shared/lib/no-fallback-error.external.js", () => require("next/dist/shared/lib/no-fallback-error.external.js"));

module.exports = mod;
}),
"[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
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
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/app-dir/link.react-server.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$api$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/api/navigation.react-server.js [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/navigation.react-server.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Breadcrumbs$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Comments$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Player$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/content.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/present.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/site.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$server$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/player/server.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$metadata$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/seo/metadata.ts [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Comments$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Comments$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
;
;
;
;
;
const dynamic = 'force-dynamic';
const asRecord = (value)=>value && typeof value === 'object' ? value : null;
const generateMetadata = async ({ params })=>{
    const site = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["currentSite"])();
    const payload = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["payloadClient"])();
    const { slug } = await params;
    const doc = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getTenantTitle"])(payload, site.tenant, slug);
    if (!doc) return {
        robots: 'noindex,follow',
        title: 'Материал не найден'
    };
    const record = asRecord(doc);
    const shared = asRecord(record.title);
    const seo = asRecord(record.seoFields) ?? record;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$metadata$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildMetadata"])({
        tenant: site.tenant,
        pageType: 'title',
        path: `/catalog/${slug}/`,
        heading: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["titleNameOf"])(doc),
        description: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["describe"])(seo.seoDescription, record.editorialIntro, shared?.factualSynopsis),
        ownText: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["plainText"])(record.editorialIntro),
        documentRobots: seo.robots ?? 'inherit'
    }, site.siteName);
};
const TitlePage = async ({ params })=>{
    const site = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["currentSite"])();
    const payload = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["payloadClient"])();
    const { slug } = await params;
    const doc = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getTenantTitle"])(payload, site.tenant, slug);
    if (!doc) (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["notFound"])();
    const record = asRecord(doc);
    const shared = asRecord(record.title);
    const name = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["titleNameOf"])(doc);
    const seasons = shared?.id ? await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["listSeasons"])(payload, shared.id) : {
        docs: []
    };
    const player = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$server$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["playerConfigFor"])(payload, site.tenant, shared);
    const intro = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$present$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["plainText"])(record.editorialIntro);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Breadcrumbs$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Breadcrumbs"], {
                origin: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$seo$2f$metadata$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["absoluteUrl"])(site.tenant, ''),
                crumbs: [
                    {
                        title: 'Главная',
                        href: '/'
                    },
                    {
                        title: 'Каталог',
                        href: '/catalog/'
                    },
                    {
                        title: name,
                        href: `/catalog/${slug}/`
                    }
                ]
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 63,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h1", {
                children: name
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 71,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "section",
                children: player.attributes ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Player$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Player"], {
                    attributes: player.attributes,
                    scriptUrl: player.scriptUrl,
                    unavailableText: "Сейчас смотреть нельзя: у этого материала нет доступного видео."
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                    lineNumber: 75,
                    columnNumber: 11
                }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                    className: "notice",
                    role: "status",
                    children: player.reason
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                    lineNumber: 81,
                    columnNumber: 11
                }, ("TURBOPACK compile-time value", void 0))
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 73,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            intro ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                        children: "О чём материал"
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 89,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        style: {
                            maxWidth: '70ch'
                        },
                        children: intro
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 90,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    asRecord(record.editorialAuthor)?.name ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "card__meta",
                        children: [
                            "Автор: ",
                            String(asRecord(record.editorialAuthor).name)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 92,
                        columnNumber: 13
                    }, ("TURBOPACK compile-time value", void 0)) : null
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 88,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : null,
            shared?.factualSynopsis ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                        children: "Описание из источника"
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 99,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        style: {
                            maxWidth: '70ch'
                        },
                        children: String(shared.factualSynopsis)
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 100,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 98,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "section",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                        children: "Сезоны и эпизоды"
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 105,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0)),
                    seasons.docs.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "notice",
                        children: "Данные о сезонах пока не переданы."
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 107,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
                        className: "list",
                        children: seasons.docs.map((season)=>{
                            const item = asRecord(season);
                            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"], {
                                    href: `/catalog/${slug}/season-${String(item.number)}/`,
                                    children: [
                                        "Сезон ",
                                        String(item.number),
                                        item.name ? ` — ${String(item.name)}` : ''
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                                    lineNumber: 114,
                                    columnNumber: 19
                                }, ("TURBOPACK compile-time value", void 0))
                            }, String(item.id), false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                                lineNumber: 113,
                                columnNumber: 17
                            }, ("TURBOPACK compile-time value", void 0));
                        })
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                        lineNumber: 109,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 104,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Comments$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Comments"], {
                site: site,
                targetType: "title",
                targetId: String(record.id),
                targetUrl: `/catalog/${slug}/`
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
                lineNumber: 125,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx",
        lineNumber: 62,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
const __TURBOPACK__default__export__ = TitlePage;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx [app-rsc] (ecmascript, Next.js Server Component)", (function(__turbopack_context__){

__turbopack_context__.n(__turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(frontend)/catalog/[slug]/page.tsx [app-rsc] (ecmascript)"));
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Breadcrumbs",
    ()=>Breadcrumbs
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/app-dir/link.react-server.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$JsonLd$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/JsonLd.tsx [app-rsc] (ecmascript)");
;
;
;
const Breadcrumbs = ({ crumbs, origin })=>{
    if (crumbs.length === 0) return null;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("nav", {
                "aria-label": "Хлебные крошки",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("ol", {
                    className: "row",
                    style: {
                        listStyle: 'none',
                        padding: 0,
                        margin: '0 0 1rem',
                        gap: '0.5rem'
                    },
                    children: crumbs.map((crumb, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                            children: [
                                index < crumbs.length - 1 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"], {
                                    href: crumb.href,
                                    children: crumb.title
                                }, void 0, false, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                                    lineNumber: 16,
                                    columnNumber: 44
                                }, ("TURBOPACK compile-time value", void 0)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    children: crumb.title
                                }, void 0, false, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                                    lineNumber: 16,
                                    columnNumber: 91
                                }, ("TURBOPACK compile-time value", void 0)),
                                index < crumbs.length - 1 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    "aria-hidden": "true",
                                    children: " / "
                                }, void 0, false, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                                    lineNumber: 17,
                                    columnNumber: 44
                                }, ("TURBOPACK compile-time value", void 0)) : null
                            ]
                        }, crumb.href, true, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                            lineNumber: 15,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)))
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                    lineNumber: 13,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                lineNumber: 12,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$JsonLd$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["JsonLd"], {
                data: {
                    '@context': 'https://schema.org',
                    '@type': 'BreadcrumbList',
                    itemListElement: crumbs.map((crumb, index)=>({
                            '@type': 'ListItem',
                            position: index + 1,
                            name: crumb.title,
                            item: `${origin}${crumb.href}`
                        }))
                }
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
                lineNumber: 22,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Breadcrumbs.tsx",
        lineNumber: 11,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
}),
"[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (client reference proxy)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CommentForm",
    ()=>CommentForm
]);
// This file is generated by next-core EcmascriptClientReferenceModule.
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-rsc] (ecmascript)");
;
const CommentForm = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call CommentForm() from the server but CommentForm is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx", "CommentForm");
}),
"[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (client reference proxy) <module evaluation>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CommentForm",
    ()=>CommentForm
]);
// This file is generated by next-core EcmascriptClientReferenceModule.
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-rsc] (ecmascript)");
;
const CommentForm = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call CommentForm() from the server but CommentForm is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx <module evaluation>", "CommentForm");
}),
"[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$CommentForm$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__$3c$module__evaluation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (client reference proxy) <module evaluation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$CommentForm$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (client reference proxy)");
;
__turbopack_context__.n(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$CommentForm$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__);
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Comments",
    ()=>Comments
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$submit$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/comments/submit.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/site.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/tenant-query.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$CommentForm$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
const Comments = async ({ site, targetType, targetId, targetUrl })=>{
    const settings = site.settings ?? {};
    if (settings.commentsEnabled === false) return null;
    const payload = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$site$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["payloadClient"])();
    const result = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFind"])(payload, {
        collection: 'comments',
        tenant: site.tenant,
        where: {
            and: [
                {
                    targetType: {
                        equals: targetType
                    }
                },
                {
                    targetId: {
                        equals: targetId
                    }
                },
                {
                    status: {
                        equals: 'published'
                    }
                }
            ]
        },
        sort: 'createdAt',
        limit: 200,
        depth: 1
    });
    const docs = result.docs;
    const byParent = new Map();
    for (const doc of docs){
        const parentId = doc.parent ? String(doc.parent.id ?? doc.parent) : 'root';
        byParent.set(parentId, [
            ...byParent.get(parentId) ?? [],
            doc
        ]);
    }
    const authorNameOf = (doc)=>{
        const author = doc.author;
        // E-mail никогда не показывается публично, даже если имя не заполнено.
        return String(author?.name ?? doc.guestName ?? 'Аноним');
    };
    const renderBranch = (parentId, level)=>{
        const branch = byParent.get(parentId) ?? [];
        if (branch.length === 0) return null;
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("ul", {
            className: "list",
            style: {
                marginLeft: level > 0 ? '1.5rem' : 0
            },
            children: branch.map((doc)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("li", {
                    className: "card",
                    style: {
                        padding: '0.75rem'
                    },
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            className: "card__meta",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                    children: authorNameOf(doc)
                                }, void 0, false, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                                    lineNumber: 62,
                                    columnNumber: 15
                                }, ("TURBOPACK compile-time value", void 0)),
                                ' ',
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("time", {
                                    dateTime: String(doc.createdAt),
                                    children: new Date(String(doc.createdAt)).toLocaleDateString('ru-RU')
                                }, void 0, false, {
                                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                                    lineNumber: 63,
                                    columnNumber: 15
                                }, ("TURBOPACK compile-time value", void 0))
                            ]
                        }, void 0, true, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                            lineNumber: 61,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            style: {
                                whiteSpace: 'pre-line',
                                margin: 0
                            },
                            children: String(doc.body ?? '')
                        }, void 0, false, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                            lineNumber: 67,
                            columnNumber: 13
                        }, ("TURBOPACK compile-time value", void 0)),
                        renderBranch(String(doc.id), level + 1)
                    ]
                }, String(doc.id), true, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                    lineNumber: 60,
                    columnNumber: 11
                }, ("TURBOPACK compile-time value", void 0)))
        }, void 0, false, {
            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
            lineNumber: 58,
            columnNumber: 7
        }, ("TURBOPACK compile-time value", void 0));
    };
    const token = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$submit$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["issueFormToken"])(process.env.PAYLOAD_SECRET ?? '', site.tenant.id, targetType, targetId, Math.floor(Date.now() / 1000));
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
        className: "section",
        id: "comments",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                children: [
                    "Комментарии (",
                    result.totalDocs,
                    ")"
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                lineNumber: 85,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            result.totalDocs === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "notice",
                children: "Пока никто не оставил комментарий."
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                lineNumber: 87,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : renderBranch('root', 0),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                children: "Оставить комментарий"
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                lineNumber: 91,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$CommentForm$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CommentForm"], {
                targetType: targetType,
                targetId: targetId,
                targetUrl: targetUrl,
                formToken: token,
                allowGuests: site.tenant.allowGuestComments,
                rulesText: String(settings.rulesText ?? 'Пишите по делу и уважайте собеседников.'),
                maxLength: Number(settings.maxLength ?? 4000)
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
                lineNumber: 92,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0))
        ]
    }, void 0, true, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Comments.tsx",
        lineNumber: 84,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/components/JsonLd.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Структурированные данные. `<` экранируется: иначе строка внутри JSON может
 * закрыть тег script и превратиться в разметку страницы.
 */ __turbopack_context__.s([
    "JsonLd",
    ()=>JsonLd
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
;
const JsonLd = ({ data })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])("script", {
        type: "application/ld+json",
        dangerouslySetInnerHTML: {
            __html: JSON.stringify(data).replace(/</g, '\\u003c')
        }
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/JsonLd.tsx",
        lineNumber: 6,
        columnNumber: 3
    }, ("TURBOPACK compile-time value", void 0));
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (client reference proxy)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Player",
    ()=>Player
]);
// This file is generated by next-core EcmascriptClientReferenceModule.
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-rsc] (ecmascript)");
;
const Player = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call Player() from the server but Player is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx", "Player");
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (client reference proxy) <module evaluation>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Player",
    ()=>Player
]);
// This file is generated by next-core EcmascriptClientReferenceModule.
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-rsc] (ecmascript)");
;
const Player = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call Player() from the server but Player is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx <module evaluation>", "Player");
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Player$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__$3c$module__evaluation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (client reference proxy) <module evaluation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Player$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-rsc] (client reference proxy)");
;
__turbopack_context__.n(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$components$2f$Player$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__);
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
"[project]/blueprints/payload-next-multisite/app/src/player/contract.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Контракт плеера CDNVideoHub.
 *
 * Значения здесь — только из переданной документации провайдера. Ни один
 * атрибут, метод или событие не придуман: если параметра нет в контракте, его
 * нельзя «предположить», это BLOCKED_PLAYER_CONTRACT.
 */ __turbopack_context__.s([
    "AGGREGATORS",
    ()=>AGGREGATORS,
    "ALLOWED_ATTRIBUTES",
    ()=>ALLOWED_ATTRIBUTES,
    "MOCK_SCRIPT_URL",
    ()=>MOCK_SCRIPT_URL,
    "PLAYER_ELEMENT",
    ()=>PLAYER_ELEMENT,
    "PLAYER_EVENTS",
    ()=>PLAYER_EVENTS,
    "PLAYER_METHODS",
    ()=>PLAYER_METHODS,
    "PLAYER_SCRIPT_URL",
    ()=>PLAYER_SCRIPT_URL,
    "PlayerContractError",
    ()=>PlayerContractError,
    "buildPlayerAttributes",
    ()=>buildPlayerAttributes,
    "resolvePlayerMode",
    ()=>resolvePlayerMode,
    "scriptUrlFor",
    ()=>scriptUrlFor
]);
const PLAYER_SCRIPT_URL = 'https://player.cdnvideohub.com/s2/stable/video-player.umd.js';
const PLAYER_ELEMENT = 'video-player';
const PLAYER_METHODS = [
    'selectSeason',
    'selectEpisode'
];
const PLAYER_EVENTS = [
    'noData'
];
const AGGREGATORS = [
    'kp',
    'mali',
    'mdl'
];
const ALLOWED_ATTRIBUTES = [
    'ident',
    'season',
    'episode',
    'data-publisher-id',
    'data-title-id',
    'data-aggregator',
    'only-voice',
    'priority-voice',
    'is-show-voice-only',
    'is-show-banner',
    'disable-licensed'
];
class PlayerContractError extends Error {
    constructor(message){
        super(`BLOCKED_PLAYER_CONTRACT: ${message}`);
    }
}
const positiveInteger = (value, field)=>{
    if (!Number.isInteger(value) || value < 1) {
        throw new PlayerContractError(`${field} должен быть целым числом от 1, получено ${value}`);
    }
    return String(value);
};
const buildPlayerAttributes = (input)=>{
    const titleId = input.titleId?.trim();
    if (!titleId) throw new PlayerContractError('не передан идентификатор тайтла');
    if (!AGGREGATORS.includes(input.aggregator)) {
        throw new PlayerContractError(`агрегатор «${input.aggregator}» отсутствует в контракте (допустимы ${AGGREGATORS.join(', ')})`);
    }
    const publisherId = input.publisherId?.trim();
    if (!publisherId) throw new PlayerContractError('не передан publisher ID');
    const attributes = {
        ident: titleId,
        'data-title-id': titleId,
        'data-publisher-id': publisherId,
        'data-aggregator': input.aggregator,
        'disable-licensed': 'false'
    };
    if (input.season !== null && input.season !== undefined) {
        attributes.season = positiveInteger(input.season, 'season');
    }
    if (input.episode !== null && input.episode !== undefined) {
        attributes.episode = positiveInteger(input.episode, 'episode');
    }
    if (input.onlyVoice) attributes['only-voice'] = input.onlyVoice;
    if (input.priorityVoice) attributes['priority-voice'] = input.priorityVoice;
    if (input.showVoiceOnly) attributes['is-show-voice-only'] = 'true';
    if (input.showBanner) attributes['is-show-banner'] = 'true';
    for (const key of Object.keys(attributes)){
        if (!ALLOWED_ATTRIBUTES.includes(key)) {
            throw new PlayerContractError(`атрибут «${key}» не описан контрактом`);
        }
    }
    return attributes;
};
const MOCK_SCRIPT_URL = '/mock/video-player.umd.js';
const resolvePlayerMode = (environment, requested)=>{
    const mode = requested === 'mock' ? 'mock' : 'live';
    if (mode === 'mock' && environment === 'production') {
        // Отказ именно технический: договорённость «в production мы не включаем mock»
        // проверить невозможно, а этот throw виден в тесте и в логе сборки.
        throw new PlayerContractError('mock-режим плеера запрещён в production');
    }
    return mode;
};
const scriptUrlFor = (mode)=>mode === 'mock' ? MOCK_SCRIPT_URL : PLAYER_SCRIPT_URL;
}),
"[project]/blueprints/payload-next-multisite/app/src/player/server.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "playerConfigFor",
    ()=>playerConfigFor
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/tenant-query.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/player/contract.ts [app-rsc] (ecmascript)");
;
;
const asRecord = (value)=>value && typeof value === 'object' ? value : null;
const playerConfigFor = async (payload, tenant, sharedTitle, position = {})=>{
    const title = asRecord(sharedTitle);
    if (!title) return {
        reason: 'Данные тайтла недоступны.'
    };
    const rights = asRecord(title.rightsRecord);
    if (!rights || rights.allowsPublication !== true) {
        // Права не подтверждены — видео не показывается вовсе. Это не ошибка рендера,
        // а осознанное состояние страницы.
        return {
            reason: 'Просмотр недоступен: права на публикацию не подтверждены.'
        };
    }
    const titleId = String(title.playbackTitleId ?? '').trim();
    const aggregator = String(title.playbackAggregator ?? '').trim();
    if (!titleId || !aggregator) {
        return {
            reason: 'Просмотр недоступен: у материала нет идентификаторов воспроизведения.'
        };
    }
    const profile = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(payload, {
        collection: 'player-profiles',
        tenant,
        depth: 1
    });
    if (!profile) return {
        reason: 'Просмотр недоступен: для сайта не настроен профиль плеера.'
    };
    const publisherRef = String(profile.publisherIdRef ?? '').trim();
    const publisherId = publisherRef ? (process.env[publisherRef] ?? '').trim() : '';
    if (!publisherId) {
        // Пустой секрет не заменяется значением по умолчанию и не «пробуется наугад».
        return {
            reason: 'Просмотр недоступен: не задан секрет publisher ID для этого сайта.'
        };
    }
    const priorityVoice = asRecord(profile.priorityVoice);
    const mode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["resolvePlayerMode"])(process.env.FACTORY_ENVIRONMENT ?? 'staging', process.env.PLAYER_MODE);
    try {
        const attributes = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildPlayerAttributes"])({
            titleId,
            aggregator,
            publisherId,
            season: position.season ?? null,
            episode: position.episode ?? null,
            priorityVoice: priorityVoice ? String(priorityVoice.playerValue ?? '').trim() || null : null,
            showVoiceOnly: profile.showVoiceOnly === true,
            showBanner: profile.showBanner === true
        });
        return {
            attributes,
            scriptUrl: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["scriptUrlFor"])(mode)
        };
    } catch (error) {
        if (error instanceof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PlayerContractError"]) return {
            reason: error.message
        };
        throw error;
    }
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

//# sourceMappingURL=%5Broot-of-the-server%5D__0-gaczn._.js.map