module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/DocumentHeader/Tabs/ShouldRenderTabs.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "ShouldRenderTabs",
    ()=>ShouldRenderTabs
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
const ShouldRenderTabs = (t0)=>{
    const { children } = t0;
    const { id: idFromContext, collectionSlug, globalSlug } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const id = idFromContext !== "create" ? idFromContext : null;
    if (collectionSlug && id || globalSlug) {
        return children;
    }
    return null;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/DocumentHeader/Tabs/Tab/TabLink.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "DocumentTabLink",
    ()=>DocumentTabLink
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
const DocumentTabLink = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(13);
    const { adminRoute, ariaLabel, baseClass, children, href: hrefFromProps, isActive: isActiveFromProps, newTab } = t0;
    const pathname = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["usePathname"])();
    const params = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useParams"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const locale = searchParams.get("locale");
    const [entityType, entitySlug, segmentThree, segmentFour] = params.segments || [];
    const isCollection = entityType === "collections";
    const t1 = `/${isCollection ? "collections" : "globals"}/${entitySlug}`;
    let t2;
    if ($[0] !== adminRoute || $[1] !== t1) {
        t2 = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
            adminRoute,
            path: t1
        });
        $[0] = adminRoute;
        $[1] = t1;
        $[2] = t2;
    } else {
        t2 = $[2];
    }
    let docPath = t2;
    if (isCollection) {
        if (segmentThree === "trash" && segmentFour) {
            docPath = docPath + `/trash/${segmentFour}`;
        } else {
            if (segmentThree) {
                docPath = docPath + `/${segmentThree}`;
            }
        }
    }
    const href = `${docPath}${hrefFromProps}`;
    const hrefWithLocale = `${href}${locale ? `?locale=${locale}` : ""}`;
    let t3;
    if ($[3] !== ariaLabel || $[4] !== baseClass || $[5] !== children || $[6] !== docPath || $[7] !== href || $[8] !== hrefWithLocale || $[9] !== isActiveFromProps || $[10] !== newTab || $[11] !== pathname) {
        const isActive = href === docPath && pathname === docPath || href !== docPath && pathname.startsWith(href) || isActiveFromProps;
        t3 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
            "aria-label": ariaLabel,
            buttonStyle: "tab",
            className: [
                baseClass,
                isActive && `${baseClass}--active`
            ].filter(Boolean).join(" "),
            disabled: isActive,
            el: !isActive || href !== pathname ? "link" : "div",
            margin: false,
            newTab,
            size: "medium",
            to: !isActive || href !== pathname ? hrefWithLocale : undefined,
            children
        });
        $[3] = ariaLabel;
        $[4] = baseClass;
        $[5] = children;
        $[6] = docPath;
        $[7] = href;
        $[8] = hrefWithLocale;
        $[9] = isActiveFromProps;
        $[10] = newTab;
        $[11] = pathname;
        $[12] = t3;
    } else {
        t3 = $[12];
    }
    return t3;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/DocumentHeader/Tabs/tabs/VersionsPill/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "VersionsPill",
    ()=>VersionsPill
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'pill-version-count';
const VersionsPill = ()=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(2);
    const { versionCount } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    if (!versionCount) {
        return null;
    }
    let t0;
    if ($[0] !== versionCount) {
        t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
            className: baseClass,
            children: versionCount
        });
        $[0] = versionCount;
        $[1] = t0;
    } else {
        t0 = $[1];
    }
    return t0;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/Nav/NavHamburger/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "NavHamburger",
    ()=>NavHamburger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const NavHamburger = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(6);
    const { baseClass } = t0;
    const { navOpen, setNavOpen } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useNav"])();
    const t1 = `${baseClass}__mobile-close`;
    let t2;
    if ($[0] !== setNavOpen) {
        t2 = ()=>{
            setNavOpen(false);
        };
        $[0] = setNavOpen;
        $[1] = t2;
    } else {
        t2 = $[1];
    }
    const t3 = !navOpen ? -1 : undefined;
    let t4;
    if ($[2] !== t1 || $[3] !== t2 || $[4] !== t3) {
        t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("button", {
            className: t1,
            onClick: t2,
            tabIndex: t3,
            type: "button",
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Hamburger"], {
                isActive: true
            })
        });
        $[2] = t1;
        $[3] = t2;
        $[4] = t3;
        $[5] = t4;
    } else {
        t4 = $[5];
    }
    return t4;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/Nav/NavWrapper/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "NavWrapper",
    ()=>NavWrapper
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const NavWrapper = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(11);
    const { baseClass, children } = props;
    const { hydrated, navOpen, navRef, shouldAnimate } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useNav"])();
    const t0 = navOpen && `${baseClass}--nav-open`;
    const t1 = shouldAnimate && `${baseClass}--nav-animate`;
    const t2 = hydrated && `${baseClass}--nav-hydrated`;
    let t3;
    if ($[0] !== baseClass || $[1] !== t0 || $[2] !== t1 || $[3] !== t2) {
        t3 = [
            baseClass,
            t0,
            t1,
            t2
        ].filter(Boolean);
        $[0] = baseClass;
        $[1] = t0;
        $[2] = t1;
        $[3] = t2;
        $[4] = t3;
    } else {
        t3 = $[4];
    }
    const t4 = t3.join(" ");
    const t5 = !navOpen ? true : undefined;
    const t6 = `${baseClass}__scroll`;
    let t7;
    if ($[5] !== children || $[6] !== navRef || $[7] !== t4 || $[8] !== t5 || $[9] !== t6) {
        t7 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("aside", {
            className: t4,
            inert: t5,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: t6,
                ref: navRef,
                children
            })
        });
        $[5] = children;
        $[6] = navRef;
        $[7] = t4;
        $[8] = t5;
        $[9] = t6;
        $[10] = t7;
    } else {
        t7 = $[10];
    }
    return t7;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/Nav/SettingsMenuButton/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "SettingsMenuButton",
    ()=>SettingsMenuButton
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'settings-menu-button';
const SettingsMenuButton = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(3);
    const { settingsMenu } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    if (!settingsMenu || settingsMenu.length === 0) {
        return null;
    }
    let t1;
    if ($[0] !== settingsMenu || $[1] !== t) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Popup"], {
            button: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["GearIcon"], {
                ariaLabel: t("general:menu")
            }),
            className: baseClass,
            horizontalAlign: "left",
            id: "settings-menu",
            size: "small",
            verticalAlign: "bottom",
            children: settingsMenu.map(_temp)
        });
        $[0] = settingsMenu;
        $[1] = t;
        $[2] = t1;
    } else {
        t1 = $[2];
    }
    return t1;
};
function _temp(item, i) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: item
    }, `settings-menu-item-${i}`);
}
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/Nav/index.client.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "DefaultNavClient",
    ()=>DefaultNavClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'nav';
const DefaultNavClient = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(13);
    const { groups, navPreferences } = t0;
    const pathname = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["usePathname"])();
    const { config: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t2, folders, routes: t3 } = t1;
    const { routes: t4 } = t2;
    const { browseByFolder: foldersRoute } = t4;
    const { admin: adminRoute } = t3;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t5;
    if ($[0] !== adminRoute || $[1] !== folders || $[2] !== foldersRoute || $[3] !== groups || $[4] !== i18n || $[5] !== navPreferences?.groups || $[6] !== pathname) {
        const folderURL = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
            adminRoute,
            path: foldersRoute
        });
        const viewingRootFolderView = pathname.startsWith(folderURL);
        let t6;
        if ($[8] !== adminRoute || $[9] !== i18n || $[10] !== navPreferences?.groups || $[11] !== pathname) {
            t6 = (t7, key)=>{
                const { entities, label } = t7;
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["NavGroup"], {
                    isOpen: navPreferences?.groups?.[label]?.open,
                    label,
                    children: entities.map((t8, i)=>{
                        const { slug, type, label: label_0 } = t8;
                        let href;
                        let id;
                        if (type === __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EntityType"].collection) {
                            href = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                                adminRoute,
                                path: `/collections/${slug}`
                            });
                            id = `nav-${slug}`;
                        }
                        if (type === __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EntityType"].global) {
                            href = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                                adminRoute,
                                path: `/globals/${slug}`
                            });
                            id = `nav-global-${slug}`;
                        }
                        const isActive = pathname.startsWith(href) && [
                            "/",
                            undefined
                        ].includes(pathname[href.length]);
                        const Label = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: [
                                isActive && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                    className: `${baseClass}__link-indicator`
                                }),
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                    className: `${baseClass}__link-label`,
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(label_0, i18n)
                                })
                            ]
                        });
                        if (pathname === href) {
                            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                className: `${baseClass}__link`,
                                id,
                                children: Label
                            }, i);
                        }
                        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Link"], {
                            className: `${baseClass}__link`,
                            href,
                            id,
                            prefetch: false,
                            children: Label
                        }, i);
                    })
                }, key);
            };
            $[8] = adminRoute;
            $[9] = i18n;
            $[10] = navPreferences?.groups;
            $[11] = pathname;
            $[12] = t6;
        } else {
            t6 = $[12];
        }
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                folders && folders.browseByFolder && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["BrowseByFolderButton"], {
                    active: viewingRootFolderView
                }),
                groups.map(t6)
            ]
        });
        $[0] = adminRoute;
        $[1] = folders;
        $[2] = foldersRoute;
        $[3] = groups;
        $[4] = i18n;
        $[5] = navPreferences?.groups;
        $[6] = pathname;
        $[7] = t5;
    } else {
        t5 = $[7];
    }
    return t5;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/templates/Default/NavHamburger/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "NavHamburger",
    ()=>NavHamburger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const NavHamburger = ()=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(2);
    const { navOpen } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useNav"])();
    let t0;
    if ($[0] !== navOpen) {
        t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Hamburger"], {
            closeIcon: "collapse",
            isActive: navOpen
        });
        $[0] = navOpen;
        $[1] = t0;
    } else {
        t0 = $[1];
    }
    return t0;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/templates/Default/Wrapper/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Wrapper",
    ()=>Wrapper
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const Wrapper = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(9);
    const { baseClass, children, className } = props;
    const { hydrated, navOpen, shouldAnimate } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useNav"])();
    const t0 = navOpen && `${baseClass}--nav-open`;
    const t1 = shouldAnimate && `${baseClass}--nav-animate`;
    const t2 = hydrated && `${baseClass}--nav-hydrated`;
    let t3;
    if ($[0] !== baseClass || $[1] !== className || $[2] !== t0 || $[3] !== t1 || $[4] !== t2) {
        t3 = [
            baseClass,
            className,
            t0,
            t1,
            t2
        ].filter(Boolean);
        $[0] = baseClass;
        $[1] = className;
        $[2] = t0;
        $[3] = t1;
        $[4] = t2;
        $[5] = t3;
    } else {
        t3 = $[5];
    }
    const t4 = t3.join(" ");
    let t5;
    if ($[6] !== children || $[7] !== t4) {
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: t4,
            children
        });
        $[6] = children;
        $[7] = t4;
        $[8] = t5;
    } else {
        t5 = $[8];
    }
    return t5;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/API/LocaleSelector/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "LocaleSelector",
    ()=>LocaleSelector
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const LocaleSelector = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(6);
    const { localeOptions, onChange } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t1;
    if ($[0] !== localeOptions || $[1] !== onChange || $[2] !== t) {
        let t2;
        if ($[4] !== onChange) {
            t2 = (value)=>onChange(value);
            $[4] = onChange;
            $[5] = t2;
        } else {
            t2 = $[5];
        }
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["SelectField"], {
            field: {
                name: "locale",
                label: t("general:locale"),
                options: localeOptions
            },
            onChange: t2,
            path: "locale"
        });
        $[0] = localeOptions;
        $[1] = onChange;
        $[2] = t;
        $[3] = t1;
    } else {
        t1 = $[3];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/API/RenderJSON/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "RenderJSON",
    ()=>RenderJSON
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const chars = {
    leftCurlyBracket: '\u007B',
    leftSquareBracket: '\u005B',
    rightCurlyBracket: '\u007D',
    rightSquareBracket: '\u005D'
};
const baseClass = 'query-inspector';
const Bracket = ({ type, comma = false, position })=>{
    const rightBracket = type === 'object' ? chars.rightCurlyBracket : chars.rightSquareBracket;
    const leftBracket = type === 'object' ? chars.leftCurlyBracket : chars.leftSquareBracket;
    const bracketToRender = position === 'end' ? rightBracket : leftBracket;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
        className: `${baseClass}__bracket ${baseClass}__bracket--position-${position}`,
        children: [
            bracketToRender,
            position === 'end' && comma ? ',' : null
        ]
    });
};
const RenderJSON = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(2);
    const { isEmpty: t1, object, objectKey, parentType: t2, trailingComma: t3 } = t0;
    const isEmpty = t1 === undefined ? false : t1;
    const parentType = t2 === undefined ? "object" : t2;
    const trailingComma = t3 === undefined ? false : t3;
    const objectKeys = object ? Object.keys(object) : [];
    const objectLength = objectKeys.length;
    const [isOpen, setIsOpen] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](true);
    const isNested = parentType === "object" || parentType === "array";
    let t4;
    if ($[0] !== isOpen) {
        t4 = ()=>setIsOpen(!isOpen);
        $[0] = isOpen;
        $[1] = t4;
    } else {
        t4 = $[1];
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("li", {
        className: isNested ? `${baseClass}__row-line--nested` : "",
        children: [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("button", {
                "aria-label": "toggle",
                className: `${baseClass}__list-toggle ${isEmpty ? `${baseClass}__list-toggle--empty` : ""}`,
                onClick: t4,
                type: "button",
                children: [
                    isEmpty ? null : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ChevronIcon"], {
                        className: `${baseClass}__toggle-row-icon ${baseClass}__toggle-row-icon--${isOpen ? "open" : "closed"}`
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                        children: [
                            objectKey && `"${objectKey}": `,
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Bracket, {
                                position: "start",
                                type: parentType
                            }),
                            isEmpty ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Bracket, {
                                comma: trailingComma,
                                position: "end",
                                type: parentType
                            }) : null
                        ]
                    })
                ]
            }),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("ul", {
                className: `${baseClass}__json-children ${isNested ? `${baseClass}__json-children--nested` : ""}`,
                children: isOpen && objectKeys.map((key, keyIndex)=>{
                    let value = object[key];
                    let type;
                    const isLastKey = keyIndex === objectLength - 1;
                    if (value === null) {
                        type = "null";
                    } else {
                        if (value instanceof Date) {
                            type = "date";
                            value = value.toISOString();
                        } else {
                            if (Array.isArray(value)) {
                                type = "array";
                            } else {
                                if (typeof value === "object") {
                                    type = "object";
                                } else {
                                    if (typeof value === "number") {
                                        type = "number";
                                    } else {
                                        if (typeof value === "boolean") {
                                            type = "boolean";
                                        } else {
                                            type = "string";
                                        }
                                    }
                                }
                            }
                        }
                    }
                    if (type === "object" || type === "array") {
                        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(RenderJSON, {
                            isEmpty: value.length === 0 || Object.keys(value).length === 0,
                            object: value,
                            objectKey: parentType === "object" ? key : undefined,
                            parentType: type,
                            trailingComma: !isLastKey
                        }, `${key}-${keyIndex}`);
                    }
                    if (type === "date" || type === "string" || type === "null" || type === "number" || type === "boolean") {
                        const parentHasKey = Boolean(parentType === "object" && key);
                        const rowClasses = [
                            `${baseClass}__row-line`,
                            `${baseClass}__value-type--${type}`,
                            `${baseClass}__row-line--${objectKey ? "nested" : "top"}`
                        ].filter(Boolean).join(" ");
                        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("li", {
                            className: rowClasses,
                            children: [
                                parentHasKey ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                    children: `"${key}": `
                                }) : null,
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                    className: `${baseClass}__value`,
                                    children: JSON.stringify(value)
                                }),
                                isLastKey ? "" : ","
                            ]
                        }, `${key}-${keyIndex}`);
                    }
                })
            }),
            !isEmpty && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                className: isNested ? `${baseClass}__bracket--nested` : "",
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Bracket, {
                    comma: trailingComma,
                    position: "end",
                    type: parentType
                })
            })
        ]
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/API/index.client.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "APIViewClient",
    ()=>APIViewClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$LocaleSelector$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/API/LocaleSelector/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$RenderJSON$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/API/RenderJSON/index.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$LocaleSelector$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$RenderJSON$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$LocaleSelector$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$RenderJSON$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
const baseClass = 'query-inspector';
const APIViewClient = ()=>{
    const { id, collectionSlug, globalSlug, initialData, isTrashed } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { code } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { config: { defaultDepth, localization, routes: { api: apiRoute }, serverURL }, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const collectionConfig = getEntityConfig({
        collectionSlug
    });
    const globalConfig = getEntityConfig({
        globalSlug
    });
    const localeOptions = localization && localization.locales.map((locale)=>({
            label: locale.label,
            value: locale.code
        }));
    let draftsEnabled = false;
    let docEndpoint = undefined;
    if (collectionConfig) {
        draftsEnabled = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["hasDraftsEnabled"])(collectionConfig);
        docEndpoint = `/${collectionSlug}/${id}`;
    }
    if (globalConfig) {
        draftsEnabled = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["hasDraftsEnabled"])(globalConfig);
        docEndpoint = `/globals/${globalSlug}`;
    }
    const [data, setData] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](initialData);
    const [draft, setDraft] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](searchParams.get('draft') === 'true');
    const [locale_0, setLocale] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](searchParams?.get('locale') || code);
    const [depth, setDepth] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](searchParams.get('depth') || defaultDepth.toString());
    const [authenticated, setAuthenticated] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](true);
    const [fullscreen, setFullscreen] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](false);
    const [origin, setOrigin] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"](serverURL || '');
    // Set the origin to the window.location.origin in useEffect to avoid hydration errors
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"](()=>{
        if (!serverURL) {
            setOrigin(window.location.origin);
        }
    }, [
        serverURL
    ]);
    const trashParam = typeof initialData?.deletedAt === 'string';
    const params = new URLSearchParams({
        depth,
        draft: String(draft),
        locale: locale_0,
        trash: trashParam ? 'true' : 'false'
    }).toString();
    const fetchURL = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
        apiRoute,
        path: `${docEndpoint}?${params}`,
        serverURL: origin
    });
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"](()=>{
        const fetchData = async ()=>{
            try {
                const res = await fetch(fetchURL, {
                    credentials: authenticated ? 'include' : 'omit',
                    headers: {
                        'Accept-Language': i18n.language
                    },
                    method: 'GET'
                });
                try {
                    const json = await res.json();
                    setData(json);
                } catch (error_0) {
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error('Error parsing response');
                    console.error(error_0); // eslint-disable-line no-console
                }
            } catch (error) {
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error('Error making request');
                console.error(error); // eslint-disable-line no-console
            }
        };
        void fetchData();
    }, [
        i18n.language,
        fetchURL,
        authenticated
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Gutter"], {
        className: [
            baseClass,
            fullscreen && `${baseClass}--fullscreen`
        ].filter(Boolean).join(' '),
        right: false,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["SetDocumentStepNav"], {
                collectionSlug: collectionSlug,
                globalLabel: globalConfig?.label,
                globalSlug: globalSlug,
                id: id,
                isTrashed: isTrashed,
                pluralLabel: collectionConfig ? collectionConfig?.labels?.plural : undefined,
                useAsTitle: collectionConfig ? collectionConfig?.admin?.useAsTitle : undefined,
                view: "API"
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: `${baseClass}__configuration`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}__api-url`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                                className: `${baseClass}__label`,
                                children: [
                                    "API URL ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["CopyToClipboard"], {
                                        value: fetchURL
                                    })
                                ]
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("a", {
                                href: fetchURL,
                                rel: "noopener noreferrer",
                                target: "_blank",
                                children: fetchURL
                            })
                        ]
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
                        initialState: {
                            authenticated: {
                                initialValue: authenticated || false,
                                valid: true,
                                value: authenticated || false
                            },
                            depth: {
                                initialValue: Number(depth || 0),
                                valid: true,
                                value: Number(depth || 0)
                            },
                            draft: {
                                initialValue: draft || false,
                                valid: true,
                                value: draft || false
                            },
                            locale: {
                                initialValue: locale_0,
                                valid: true,
                                value: locale_0
                            }
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                            className: `${baseClass}__form-fields`,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                    className: `${baseClass}__filter-query-checkboxes`,
                                    children: [
                                        draftsEnabled && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["CheckboxField"], {
                                            field: {
                                                name: 'draft',
                                                label: t('version:draft')
                                            },
                                            onChange: ()=>setDraft(!draft),
                                            path: "draft"
                                        }),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["CheckboxField"], {
                                            field: {
                                                name: 'authenticated',
                                                label: t('authentication:authenticated')
                                            },
                                            onChange: ()=>setAuthenticated(!authenticated),
                                            path: "authenticated"
                                        })
                                    ]
                                }),
                                localeOptions && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$LocaleSelector$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["LocaleSelector"], {
                                    localeOptions: localeOptions,
                                    onChange: setLocale
                                }),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["NumberField"], {
                                    field: {
                                        name: 'depth',
                                        admin: {
                                            step: 1
                                        },
                                        label: t('general:depth'),
                                        max: 10,
                                        min: 0
                                    },
                                    onChange: (value)=>setDepth(value?.toString()),
                                    path: "depth"
                                })
                            ]
                        })
                    })
                ]
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: `${baseClass}__results-wrapper`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__toggle-fullscreen-button-container`,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("button", {
                            "aria-label": "toggle fullscreen",
                            className: `${baseClass}__toggle-fullscreen-button`,
                            onClick: ()=>setFullscreen(!fullscreen),
                            type: "button",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["MinimizeMaximizeIcon"], {
                                isMinimized: !fullscreen
                            })
                        })
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__results`,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$API$2f$RenderJSON$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderJSON"], {
                            object: data
                        })
                    })
                ]
            })
        ]
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Edit/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "EditView",
    ()=>EditView
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
const EditView = (props)=>{
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["DefaultEditView"], {
        ...props
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/NotFound/index.client.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "NotFoundClient",
    ()=>NotFoundClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'not-found';
const NotFoundClient = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(10);
    const { marginTop: t0 } = props;
    const marginTop = t0 === undefined ? "large" : t0;
    const { setStepNav } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useStepNav"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { routes: t2 } = t1;
    const { admin: adminRoute } = t2;
    let t3;
    let t4;
    if ($[0] !== setStepNav || $[1] !== t) {
        t3 = ()=>{
            setStepNav([
                {
                    label: t("general:notFound")
                }
            ]);
        };
        t4 = [
            setStepNav,
            t
        ];
        $[0] = setStepNav;
        $[1] = t;
        $[2] = t3;
        $[3] = t4;
    } else {
        t3 = $[2];
        t4 = $[3];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(t3, t4);
    const t5 = marginTop && `${baseClass}--margin-top-${marginTop}`;
    let t6;
    if ($[4] !== t5) {
        t6 = [
            baseClass,
            t5
        ].filter(Boolean);
        $[4] = t5;
        $[5] = t6;
    } else {
        t6 = $[5];
    }
    const t7 = t6.join(" ");
    let t8;
    if ($[6] !== adminRoute || $[7] !== t || $[8] !== t7) {
        t8 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: t7,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Gutter"], {
                className: `${baseClass}__wrap`,
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}__content`,
                        children: [
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("h1", {
                                children: t("general:nothingFound")
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("p", {
                                children: t("general:sorryNotFound")
                            })
                        ]
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                        className: `${baseClass}__button`,
                        el: "link",
                        size: "large",
                        to: adminRoute,
                        children: t("general:backToDashboard")
                    })
                ]
            })
        });
        $[6] = adminRoute;
        $[7] = t;
        $[8] = t7;
        $[9] = t8;
    } else {
        t8 = $[9];
    }
    return t8;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SelectedLocalesContext",
    ()=>SelectedLocalesContext,
    "useSelectedLocales",
    ()=>useSelectedLocales
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
'use client';
;
const SelectedLocalesContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["createContext"])({
    selectedLocales: []
});
const useSelectedLocales = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["use"])(SelectedLocalesContext);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SetStepNav.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "SetStepNav",
    ()=>SetStepNav
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const SetStepNav = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(24);
    const { id, collectionConfig, globalConfig, isTrashed, versionToCreatedAtFormatted, versionToID } = t0;
    const { config } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { setStepNav } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useStepNav"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    let t1;
    if ($[0] !== collectionConfig || $[1] !== config || $[2] !== globalConfig || $[3] !== i18n || $[4] !== id || $[5] !== isTrashed || $[6] !== setStepNav || $[7] !== t || $[8] !== title || $[9] !== versionToCreatedAtFormatted) {
        t1 = ()=>{
            const { routes: t2 } = config;
            const { admin: adminRoute } = t2;
            if (collectionConfig) {
                const collectionSlug = collectionConfig.slug;
                const pluralLabel = collectionConfig.labels?.plural;
                const docBasePath = isTrashed ? `/collections/${collectionSlug}/trash/${id}` : `/collections/${collectionSlug}/${id}`;
                const nav = [
                    {
                        label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(pluralLabel, i18n),
                        url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                            adminRoute,
                            path: `/collections/${collectionSlug}`
                        })
                    }
                ];
                if (isTrashed) {
                    nav.push({
                        label: t("general:trash"),
                        url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                            adminRoute,
                            path: `/collections/${collectionSlug}/trash`
                        })
                    });
                }
                nav.push({
                    label: title,
                    url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                        adminRoute,
                        path: docBasePath
                    })
                }, {
                    label: t("version:versions"),
                    url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                        adminRoute,
                        path: `${docBasePath}/versions`
                    })
                }, {
                    label: versionToCreatedAtFormatted,
                    url: undefined
                });
                setStepNav(nav);
                return;
            }
            if (globalConfig) {
                const globalSlug = globalConfig.slug;
                setStepNav([
                    {
                        label: globalConfig.label,
                        url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                            adminRoute,
                            path: `/globals/${globalSlug}`
                        })
                    },
                    {
                        label: t("version:versions"),
                        url: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                            adminRoute,
                            path: `/globals/${globalSlug}/versions`
                        })
                    },
                    {
                        label: versionToCreatedAtFormatted
                    }
                ]);
            }
        };
        $[0] = collectionConfig;
        $[1] = config;
        $[2] = globalConfig;
        $[3] = i18n;
        $[4] = id;
        $[5] = isTrashed;
        $[6] = setStepNav;
        $[7] = t;
        $[8] = title;
        $[9] = versionToCreatedAtFormatted;
        $[10] = t1;
    } else {
        t1 = $[10];
    }
    let t2;
    if ($[11] !== collectionConfig || $[12] !== config || $[13] !== globalConfig || $[14] !== i18n || $[15] !== id || $[16] !== isTrashed || $[17] !== locale || $[18] !== setStepNav || $[19] !== t || $[20] !== title || $[21] !== versionToCreatedAtFormatted || $[22] !== versionToID) {
        t2 = [
            config,
            setStepNav,
            id,
            isTrashed,
            locale,
            t,
            i18n,
            collectionConfig,
            globalConfig,
            title,
            versionToCreatedAtFormatted,
            versionToID
        ];
        $[11] = collectionConfig;
        $[12] = config;
        $[13] = globalConfig;
        $[14] = i18n;
        $[15] = id;
        $[16] = isTrashed;
        $[17] = locale;
        $[18] = setStepNav;
        $[19] = t;
        $[20] = title;
        $[21] = versionToCreatedAtFormatted;
        $[22] = versionToID;
        $[23] = t2;
    } else {
        t2 = $[23];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(t1, t2);
    return null;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "DefaultVersionView",
    ()=>DefaultVersionView
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Restore$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Restore/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectComparison/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectLocales$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectLocales/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SetStepNav$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SetStepNav.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Restore$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectLocales$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SetStepNav$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Restore$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectLocales$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SetStepNav$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
;
;
const baseClass = 'view-version';
const DefaultVersionView = ({ canUpdate, modifiedOnly: modifiedOnlyProp, RenderedDiff, selectedLocales: selectedLocalesFromProps, versionFromCreatedAt, versionFromID, versionFromOptions, versionToCreatedAt, versionToCreatedAtFormatted, VersionToCreatedAtLabel, versionToID, versionToStatus })=>{
    const { config, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { code } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [locales, setLocales] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])([]);
    const [localeSelectorOpen, setLocaleSelectorOpen] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].useState(false);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (config.localization) {
            const updatedLocales = config.localization.locales.map((locale)=>{
                let label = locale.label;
                if (typeof locale.label !== 'string' && locale.label[code]) {
                    label = locale.label[code];
                }
                return {
                    name: locale.code,
                    Label: label,
                    selected: selectedLocalesFromProps.includes(locale.code)
                };
            });
            setLocales(updatedLocales);
        }
    }, [
        code,
        config.localization,
        selectedLocalesFromProps
    ]);
    const { id: originalDocID, collectionSlug, globalSlug, isTrashed } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useRouteTransition"])();
    const { collectionConfig, globalConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useMemo"])(()=>{
        return {
            collectionConfig: getEntityConfig({
                collectionSlug
            }),
            globalConfig: getEntityConfig({
                globalSlug
            })
        };
    }, [
        collectionSlug,
        globalSlug,
        getEntityConfig
    ]);
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRouter"])();
    const pathname = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["usePathname"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const [modifiedOnly, setModifiedOnly] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(modifiedOnlyProp);
    const updateSearchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((args)=>{
        // If the selected comparison doc or locales change, update URL params so that version page
        // This is so that RSC can update the version comparison state
        const current = new URLSearchParams(Array.from(searchParams.entries()));
        if (args?.versionFromID) {
            current.set('versionFrom', args?.versionFromID);
        }
        if (args?.selectedLocales) {
            if (!args.selectedLocales.length) {
                current.delete('localeCodes');
            } else {
                const selectedLocaleCodes = [];
                for (const locale_0 of args.selectedLocales){
                    if (locale_0.selected) {
                        selectedLocaleCodes.push(locale_0.name);
                    }
                }
                current.set('localeCodes', JSON.stringify(selectedLocaleCodes));
            }
        }
        if (args?.modifiedOnly === false) {
            current.set('modifiedOnly', 'false');
        } else if (args?.modifiedOnly === true) {
            current.delete('modifiedOnly');
        }
        const search = current.toString();
        const query = search ? `?${search}` : '';
        startRouteTransition(()=>router.push(`${pathname}${query}`));
    }, [
        pathname,
        router,
        searchParams,
        startRouteTransition
    ]);
    const onToggleModifiedOnly = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((event)=>{
        const newModified = event.target.checked;
        setModifiedOnly(newModified);
        updateSearchParams({
            modifiedOnly: newModified
        });
    }, [
        updateSearchParams
    ]);
    const onChangeSelectedLocales = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(({ locales: locales_0 })=>{
        setLocales(locales_0);
        updateSearchParams({
            selectedLocales: locales_0
        });
    }, [
        updateSearchParams
    ]);
    const onChangeVersionFrom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((val)=>{
        updateSearchParams({
            versionFromID: val.value
        });
    }, [
        updateSearchParams
    ]);
    const { localization } = config;
    const versionToTimeAgo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useMemo"])(()=>t('version:versionAgo', {
            distance: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatTimeToNow"])({
                date: versionToCreatedAt,
                i18n
            })
        }), [
        versionToCreatedAt,
        i18n,
        t
    ]);
    const versionFromTimeAgo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useMemo"])(()=>versionFromCreatedAt ? t('version:versionAgo', {
            distance: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatTimeToNow"])({
                date: versionFromCreatedAt,
                i18n
            })
        }) : undefined, [
        versionFromCreatedAt,
        i18n,
        t
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("main", {
        className: baseClass,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Gutter"], {
                className: `${baseClass}-controls-top`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}-controls-top__wrapper`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("h2", {
                                children: i18n.t('version:compareVersions')
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                className: `${baseClass}-controls-top__wrapper-actions`,
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                        className: `${baseClass}__modifiedCheckBox`,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["CheckboxInput"], {
                                            checked: modifiedOnly,
                                            id: 'modifiedOnly',
                                            label: i18n.t('version:modifiedOnly'),
                                            onToggle: onToggleModifiedOnly
                                        })
                                    }),
                                    localization && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
                                        "aria-controls": `${baseClass}-locales`,
                                        "aria-expanded": localeSelectorOpen,
                                        className: `${baseClass}__toggle-locales`,
                                        icon: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ChevronIcon"], {
                                            direction: localeSelectorOpen ? 'up' : 'down'
                                        }),
                                        onClick: ()=>setLocaleSelectorOpen((localeSelectorOpen_0)=>!localeSelectorOpen_0),
                                        pillStyle: "light",
                                        size: "small",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                                                className: `${baseClass}__toggle-locales-label`,
                                                children: [
                                                    t('general:locales'),
                                                    ":",
                                                    ' '
                                                ]
                                            }),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                                className: `${baseClass}__toggle-locales-list`,
                                                children: locales.filter((locale_1)=>locale_1.selected).map((locale_2)=>locale_2.name).join(', ')
                                            })
                                        ]
                                    })
                                ]
                            })
                        ]
                    }),
                    localization && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectLocales$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectLocales"], {
                        locales: locales,
                        localeSelectorOpen: localeSelectorOpen,
                        onChange: onChangeSelectedLocales
                    })
                ]
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Gutter"], {
                className: `${baseClass}-controls-bottom`,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                    className: `${baseClass}-controls-bottom__wrapper`,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                            className: `${baseClass}__version-from`,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                    className: `${baseClass}__version-from-labels`,
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                            children: t('version:comparingAgainst')
                                        }),
                                        versionFromTimeAgo && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                            className: `${baseClass}__time-elapsed`,
                                            children: versionFromTimeAgo
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectComparison"], {
                                    collectionSlug: collectionSlug,
                                    docID: originalDocID,
                                    globalSlug: globalSlug,
                                    onChange: onChangeVersionFrom,
                                    versionFromID: versionFromID,
                                    versionFromOptions: versionFromOptions
                                })
                            ]
                        }),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                            className: `${baseClass}__version-to`,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                    className: `${baseClass}__version-to-labels`,
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                            children: t('version:currentlyViewing')
                                        }),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                            className: `${baseClass}__time-elapsed`,
                                            children: versionToTimeAgo
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                    className: `${baseClass}__version-to-version`,
                                    children: [
                                        VersionToCreatedAtLabel,
                                        canUpdate && !isTrashed && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Restore$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Restore"], {
                                            className: `${baseClass}__restore`,
                                            collectionConfig: collectionConfig,
                                            globalConfig: globalConfig,
                                            label: collectionConfig?.labels.singular || globalConfig?.label,
                                            originalDocID: originalDocID,
                                            status: versionToStatus,
                                            versionDateFormatted: versionToCreatedAtFormatted,
                                            versionID: versionToID
                                        })
                                    ]
                                })
                            ]
                        })
                    ]
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SetStepNav$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SetStepNav"], {
                collectionConfig: collectionConfig,
                globalConfig: globalConfig,
                id: originalDocID,
                isTrashed: isTrashed,
                versionToCreatedAtFormatted: versionToCreatedAtFormatted,
                versionToID: versionToID
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Gutter"], {
                className: `${baseClass}__diff-wrap`,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["SelectedLocalesContext"], {
                    value: {
                        selectedLocales: locales.map((locale_3)=>locale_3.name)
                    },
                    children: versionToCreatedAt && RenderedDiff
                })
            })
        ]
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/DiffCollapser/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "DiffCollapser",
    ()=>DiffCollapser
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$countChangedFields$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/countChangedFields.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$countChangedFields$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$countChangedFields$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
const baseClass = 'diff-collapser';
const DiffCollapser = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(19);
    const { children, field, fields, hideGutter: t1, initCollapsed: t2, isIterable: t3, Label, locales, parentIsLocalized, valueFrom, valueTo } = t0;
    const hideGutter = t1 === undefined ? false : t1;
    const initCollapsed = t2 === undefined ? false : t2;
    const isIterable = t3 === undefined ? false : t3;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [isCollapsed, setIsCollapsed] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(initCollapsed);
    const { config } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    let t4;
    if ($[0] !== Label || $[1] !== children || $[2] !== config || $[3] !== field || $[4] !== fields || $[5] !== hideGutter || $[6] !== isCollapsed || $[7] !== isIterable || $[8] !== locales || $[9] !== parentIsLocalized || $[10] !== t || $[11] !== valueFrom || $[12] !== valueTo) {
        let changeCount;
        if (isIterable) {
            if (!(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsArrayType"])(field) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsBlockType"])(field)) {
                throw new Error("DiffCollapser: field must be an array or blocks field when isIterable is true");
            }
            const valueFromRows = valueFrom ?? [];
            const valueToRows = valueTo ?? [];
            if (!Array.isArray(valueFromRows) || !Array.isArray(valueToRows)) {
                throw new Error("DiffCollapser: valueFrom and valueTro must be arrays when isIterable is true");
            }
            changeCount = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$countChangedFields$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["countChangedFieldsInRows"])({
                config,
                field,
                locales,
                parentIsLocalized,
                valueFromRows,
                valueToRows
            });
        } else {
            changeCount = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$countChangedFields$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["countChangedFields"])({
                config,
                fields,
                locales,
                parentIsLocalized,
                valueFrom,
                valueTo
            });
        }
        const t5 = isCollapsed && `${baseClass}__content--is-collapsed`;
        const t6 = hideGutter && `${baseClass}__content--hide-gutter`;
        let t7;
        if ($[14] !== t5 || $[15] !== t6) {
            t7 = [
                `${baseClass}__content`,
                t5,
                t6
            ].filter(Boolean);
            $[14] = t5;
            $[15] = t6;
            $[16] = t7;
        } else {
            t7 = $[16];
        }
        const contentClassNames = t7.join(" ");
        let t8;
        if ($[17] !== isCollapsed) {
            t8 = ()=>setIsCollapsed(!isCollapsed);
            $[17] = isCollapsed;
            $[18] = t8;
        } else {
            t8 = $[18];
        }
        t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: baseClass,
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldDiffLabel"], {
                    children: [
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("button", {
                            "aria-label": isCollapsed ? "Expand" : "Collapse",
                            className: `${baseClass}__toggle-button`,
                            onClick: t8,
                            type: "button",
                            children: [
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                    className: `${baseClass}__label`,
                                    children: Label
                                }),
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ChevronIcon"], {
                                    direction: isCollapsed ? "right" : "down",
                                    size: "small"
                                })
                            ]
                        }),
                        changeCount > 0 && isCollapsed && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}__field-change-count`,
                            children: t("version:changedFieldsCount", {
                                count: changeCount
                            })
                        })
                    ]
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: contentClassNames,
                    children
                })
            ]
        });
        $[0] = Label;
        $[1] = children;
        $[2] = config;
        $[3] = field;
        $[4] = fields;
        $[5] = hideGutter;
        $[6] = isCollapsed;
        $[7] = isIterable;
        $[8] = locales;
        $[9] = parentIsLocalized;
        $[10] = t;
        $[11] = valueFrom;
        $[12] = valueTo;
        $[13] = t4;
    } else {
        t4 = $[13];
    }
    return t4;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RenderVersionFieldsToDiff",
    ()=>RenderVersionFieldsToDiff
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export f as ShimmerEffect>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
'use client';
;
;
const baseClass = 'render-field-diffs';
;
;
const RenderVersionFieldsToDiff = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(6);
    const { parent: t1, versionFields } = t0;
    const parent = t1 === undefined ? false : t1;
    const [hasMounted, setHasMounted] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].useState(false);
    let t2;
    let t3;
    if ($[0] === Symbol.for("react.memo_cache_sentinel")) {
        t2 = ()=>{
            setHasMounted(true);
        };
        t3 = [];
        $[0] = t2;
        $[1] = t3;
    } else {
        t2 = $[0];
        t3 = $[1];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(t2, t3);
    const t4 = `${baseClass}${parent ? ` ${baseClass}--parent` : ""}`;
    let t5;
    if ($[2] !== hasMounted || $[3] !== t4 || $[4] !== versionFields) {
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: t4,
            children: !hasMounted ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__["ShimmerEffect"], {
                    height: "8rem",
                    width: "100%"
                })
            }) : versionFields?.map(_temp)
        });
        $[2] = hasMounted;
        $[3] = t4;
        $[4] = versionFields;
        $[5] = t5;
    } else {
        t5 = $[5];
    }
    return t5;
};
function _temp(field, fieldIndex) {
    if (field.fieldByLocale) {
        const LocaleComponents = [];
        for (const [locale, baseField] of Object.entries(field.fieldByLocale)){
            LocaleComponents.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: `${baseClass}__locale`,
                "data-field-path": baseField.path,
                "data-locale": locale,
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: `${baseClass}__locale-value`,
                    children: baseField.CustomComponent
                })
            }, [
                locale,
                fieldIndex
            ].join("-")));
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: `${baseClass}__field`,
            children: LocaleComponents
        }, fieldIndex);
    } else {
        if (field.field) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: `${baseClass}__field field__${field.field.type}`,
                "data-field-path": field.field.path,
                children: field.field.CustomComponent
            }, fieldIndex);
        }
    }
    return null;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Collapsible/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Collapsible",
    ()=>Collapsible
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/DiffCollapser/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'collapsible-diff';
const Collapsible = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(8);
    const { baseVersionField, comparisonValue: valueFrom, field, parentIsLocalized, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { selectedLocales } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSelectedLocales"])();
    if (!baseVersionField.fields?.length) {
        return null;
    }
    let t1;
    if ($[0] !== baseVersionField.fields || $[1] !== field || $[2] !== i18n || $[3] !== parentIsLocalized || $[4] !== selectedLocales || $[5] !== valueFrom || $[6] !== valueTo) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: baseClass,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DiffCollapser"], {
                fields: field.fields,
                Label: "label" in field && field.label && typeof field.label !== "function" && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(field.label, i18n)
                }),
                locales: selectedLocales,
                parentIsLocalized: parentIsLocalized || field.localized,
                valueFrom,
                valueTo,
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderVersionFieldsToDiff"], {
                    versionFields: baseVersionField.fields
                })
            })
        });
        $[0] = baseVersionField.fields;
        $[1] = field;
        $[2] = i18n;
        $[3] = parentIsLocalized;
        $[4] = selectedLocales;
        $[5] = valueFrom;
        $[6] = valueTo;
        $[7] = t1;
    } else {
        t1 = $[7];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Date/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "DateDiffComponent",
    ()=>DateDiffComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const baseClass = 'date-diff';
const DateDiffComponent = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(7);
    const { comparisonValue: valueFrom, field, locale, nestingLevel, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t2 } = t1;
    const { dateFormat } = t2;
    const formattedFromDate = valueFrom ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatDate"])({
        date: typeof valueFrom === "string" ? new Date(valueFrom) : valueFrom,
        i18n,
        pattern: dateFormat
    }) : "";
    const formattedToDate = valueTo ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatDate"])({
        date: typeof valueTo === "string" ? new Date(valueTo) : valueTo,
        i18n,
        pattern: dateFormat
    }) : "";
    const escapedFromDate = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(formattedFromDate);
    const escapedToDate = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(formattedToDate);
    const t3 = `<div class="${baseClass}" data-enable-match="true" data-date="${escapedFromDate}"><p>` + escapedFromDate + "</p></div>";
    const t4 = `<div class="${baseClass}" data-enable-match="true" data-date="${escapedToDate}"><p>` + escapedToDate + "</p></div>";
    let t5;
    if ($[0] !== field.label || $[1] !== i18n || $[2] !== locale || $[3] !== nestingLevel || $[4] !== t3 || $[5] !== t4) {
        const { From, To } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getHTMLDiffComponents"])({
            fromHTML: t3,
            postProcess: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["unescapeDiffHTML"],
            toHTML: t4,
            tokenizeByCharacter: false
        });
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldDiffContainer"], {
            className: baseClass,
            From,
            i18n,
            label: {
                label: field.label,
                locale
            },
            nestingLevel,
            To
        });
        $[0] = field.label;
        $[1] = i18n;
        $[2] = locale;
        $[3] = nestingLevel;
        $[4] = t3;
        $[5] = t4;
        $[6] = t5;
    } else {
        t5 = $[6];
    }
    return t5;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Group/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Group",
    ()=>Group
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/DiffCollapser/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'group-diff';
const Group = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(9);
    const { baseVersionField, comparisonValue: valueFrom, field, locale, parentIsLocalized, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { selectedLocales } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSelectedLocales"])();
    let t1;
    if ($[0] !== baseVersionField.fields || $[1] !== field || $[2] !== i18n || $[3] !== locale || $[4] !== parentIsLocalized || $[5] !== selectedLocales || $[6] !== valueFrom || $[7] !== valueTo) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: baseClass,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DiffCollapser"], {
                fields: field.fields,
                Label: "label" in field && field.label && typeof field.label !== "function" ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                    children: [
                        locale && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}__locale-label`,
                            children: locale
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(field.label, i18n)
                    ]
                }) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                    className: `${baseClass}__locale-label ${baseClass}__locale-label--no-label`,
                    children: [
                        "<",
                        i18n.t("version:noLabelGroup"),
                        ">"
                    ]
                }),
                locales: selectedLocales,
                parentIsLocalized: parentIsLocalized || field.localized,
                valueFrom,
                valueTo,
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderVersionFieldsToDiff"], {
                    versionFields: baseVersionField.fields
                })
            })
        });
        $[0] = baseVersionField.fields;
        $[1] = field;
        $[2] = i18n;
        $[3] = locale;
        $[4] = parentIsLocalized;
        $[5] = selectedLocales;
        $[6] = valueFrom;
        $[7] = valueTo;
        $[8] = t1;
    } else {
        t1 = $[8];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Iterable/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Iterable",
    ()=>Iterable
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/DiffCollapser/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/getFieldsForRowComparison.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
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
const baseClass = 'iterable-diff';
const Iterable = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(12);
    const { baseVersionField, comparisonValue: valueFrom, field, locale, parentIsLocalized, versionValue: valueTo } = t0;
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { selectedLocales } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSelectedLocales"])();
    const { config } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    if (!(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsArrayType"])(field) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsBlockType"])(field)) {
        throw new Error(`Expected field to be an array or blocks type but got: ${field.type}`);
    }
    const valueToRowCount = Array.isArray(valueTo) ? valueTo.length : 0;
    const valueFromRowCount = Array.isArray(valueFrom) ? valueFrom.length : 0;
    const maxRows = Math.max(valueToRowCount, valueFromRowCount);
    let t1;
    if ($[0] !== baseVersionField || $[1] !== config || $[2] !== field || $[3] !== i18n || $[4] !== locale || $[5] !== maxRows || $[6] !== parentIsLocalized || $[7] !== selectedLocales || $[8] !== t || $[9] !== valueFrom || $[10] !== valueTo) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: baseClass,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DiffCollapser"], {
                field,
                isIterable: true,
                Label: "label" in field && field.label && typeof field.label !== "function" && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                    children: [
                        locale && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}__locale-label`,
                            children: locale
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(field.label, i18n)
                    ]
                }),
                locales: selectedLocales,
                parentIsLocalized,
                valueFrom,
                valueTo,
                children: [
                    maxRows > 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__rows`,
                        children: Array.from({
                            length: maxRows
                        }, (_, i)=>{
                            const valueToRow = valueTo?.[i] || {};
                            const valueFromRow = valueFrom?.[i] || {};
                            const { fields, versionFields } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getFieldsForRowComparison"])({
                                baseVersionField,
                                config,
                                field,
                                row: i,
                                valueFromRow,
                                valueToRow
                            });
                            if (!versionFields?.length) {
                                return null;
                            }
                            const rowNumber = String(i + 1).padStart(2, "0");
                            const rowLabel = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsArrayType"])(field) ? `${t("general:item")} ${rowNumber}` : `${t("fields:block")} ${rowNumber}`;
                            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                className: `${baseClass}__row`,
                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DiffCollapser"], {
                                    fields,
                                    hideGutter: true,
                                    Label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                        className: `${baseClass}-label-container`,
                                        children: [
                                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                                className: `${baseClass}-label-prefix`
                                            }),
                                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                                className: `${baseClass}__label`,
                                                children: rowLabel
                                            })
                                        ]
                                    }),
                                    locales: selectedLocales,
                                    parentIsLocalized: parentIsLocalized || field.localized,
                                    valueFrom: valueFromRow,
                                    valueTo: valueToRow,
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderVersionFieldsToDiff"], {
                                        versionFields
                                    })
                                })
                            }, i);
                        })
                    }),
                    maxRows === 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__no-rows`,
                        children: i18n.t("version:noRowsFound", {
                            label: "labels" in field && field.labels?.plural ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(field.labels.plural, i18n) : i18n.t("general:rows")
                        })
                    })
                ]
            })
        });
        $[0] = baseVersionField;
        $[1] = config;
        $[2] = field;
        $[3] = i18n;
        $[4] = locale;
        $[5] = maxRows;
        $[6] = parentIsLocalized;
        $[7] = selectedLocales;
        $[8] = t;
        $[9] = valueFrom;
        $[10] = valueTo;
        $[11] = t1;
    } else {
        t1 = $[11];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Row/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Row",
    ()=>Row
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)");
'use client';
;
;
;
const baseClass = 'row-diff';
const Row = ({ baseVersionField })=>{
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
        className: baseClass,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderVersionFieldsToDiff"], {
            versionFields: baseVersionField.fields
        })
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Select/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Select",
    ()=>Select
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const baseClass = 'select-diff';
const getOptionsToRender = (value, options, hasMany)=>{
    if (hasMany && Array.isArray(value)) {
        return value.map((val)=>options.find((option)=>(typeof option === 'string' ? option : option.value) === val) || String(val));
    }
    return options.find((option)=>(typeof option === 'string' ? option : option.value) === value) || String(value);
};
/**
 * Translates option labels while ensuring they are strings.
 * If `options.label` is a JSX element, it falls back to `options.value` because `DiffViewer`
 * expects all values to be strings.
 */ const getTranslatedOptions = (options, i18n)=>{
    if (Array.isArray(options)) {
        return options.map((option)=>{
            if (typeof option === 'string') {
                return option;
            }
            const translatedLabel = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(option.label, i18n);
            // Ensure the result is a string, otherwise use option.value
            return typeof translatedLabel === 'string' ? translatedLabel : option.value;
        }).join(', ');
    }
    if (typeof options === 'string') {
        return options;
    }
    const translatedLabel = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(options.label, i18n);
    return typeof translatedLabel === 'string' ? translatedLabel : options.value;
};
const Select = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(7);
    const { comparisonValue: valueFrom, field, locale, nestingLevel, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const options = "options" in field && field.options;
    const renderedValueFrom = typeof valueFrom !== "undefined" ? getTranslatedOptions(getOptionsToRender(typeof valueFrom === "string" ? valueFrom : JSON.stringify(valueFrom), options, field.hasMany), i18n) : "";
    const renderedValueTo = typeof valueTo !== "undefined" ? getTranslatedOptions(getOptionsToRender(typeof valueTo === "string" ? valueTo : JSON.stringify(valueTo), options, field.hasMany), i18n) : "";
    const t1 = "<p>" + (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(renderedValueFrom) + "</p>";
    const t2 = "<p>" + (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(renderedValueTo) + "</p>";
    let t3;
    if ($[0] !== field.label || $[1] !== i18n || $[2] !== locale || $[3] !== nestingLevel || $[4] !== t1 || $[5] !== t2) {
        const { From, To } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getHTMLDiffComponents"])({
            fromHTML: t1,
            postProcess: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["unescapeDiffHTML"],
            toHTML: t2,
            tokenizeByCharacter: true
        });
        t3 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldDiffContainer"], {
            className: baseClass,
            From,
            i18n,
            label: {
                label: field.label,
                locale
            },
            nestingLevel,
            To
        });
        $[0] = field.label;
        $[1] = i18n;
        $[2] = locale;
        $[3] = nestingLevel;
        $[4] = t1;
        $[5] = t2;
        $[6] = t3;
    } else {
        t3 = $[6];
    }
    return t3;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Tabs/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Tabs",
    ()=>Tabs
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Default/SelectedLocalesContext.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/DiffCollapser/index.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/RenderVersionFieldsToDiff.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'tabs-diff';
const Tabs = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(13);
    const { baseVersionField, comparisonValue: valueFrom, field, versionValue: valueTo } = props;
    const { selectedLocales } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSelectedLocales"])();
    let t0;
    if ($[0] !== baseVersionField.tabs || $[1] !== field || $[2] !== props || $[3] !== selectedLocales || $[4] !== valueFrom || $[5] !== valueTo) {
        let t1;
        if ($[7] !== field || $[8] !== props || $[9] !== selectedLocales || $[10] !== valueFrom || $[11] !== valueTo) {
            t1 = (tab, i)=>{
                if (!tab?.fields?.length) {
                    return null;
                }
                const fieldTab = field.tabs?.[i];
                if (!fieldTab) {
                    return null;
                }
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: `${baseClass}__tab`,
                    children: (()=>{
                        if ("name" in fieldTab && selectedLocales && fieldTab.localized) {
                            return selectedLocales.map((locale, index)=>{
                                const localizedTabProps = {
                                    ...props,
                                    comparisonValue: valueFrom?.[tab.name]?.[locale],
                                    fieldTab,
                                    locale,
                                    tab,
                                    versionValue: valueTo?.[tab.name]?.[locale]
                                };
                                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                    className: `${baseClass}__tab-locale`,
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                        className: `${baseClass}__tab-locale-value`,
                                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Tab, {
                                            ...localizedTabProps
                                        }, locale)
                                    })
                                }, [
                                    locale,
                                    index
                                ].join("-"));
                            });
                        } else {
                            if ("name" in tab && tab.name) {
                                const namedTabProps = {
                                    ...props,
                                    comparisonValue: valueFrom?.[tab.name],
                                    fieldTab,
                                    tab,
                                    versionValue: valueTo?.[tab.name]
                                };
                                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Tab, {
                                    ...namedTabProps
                                }, i);
                            } else {
                                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Tab, {
                                    fieldTab,
                                    ...props,
                                    tab
                                }, i);
                            }
                        }
                    })()
                }, i);
            };
            $[7] = field;
            $[8] = props;
            $[9] = selectedLocales;
            $[10] = valueFrom;
            $[11] = valueTo;
            $[12] = t1;
        } else {
            t1 = $[12];
        }
        t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: baseClass,
            children: baseVersionField.tabs.map(t1)
        });
        $[0] = baseVersionField.tabs;
        $[1] = field;
        $[2] = props;
        $[3] = selectedLocales;
        $[4] = valueFrom;
        $[5] = valueTo;
        $[6] = t0;
    } else {
        t0 = $[6];
    }
    return t0;
};
const Tab = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(10);
    const { comparisonValue: valueFrom, fieldTab, locale, parentIsLocalized, tab, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { selectedLocales } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$Default$2f$SelectedLocalesContext$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSelectedLocales"])();
    if (!tab.fields?.length) {
        return null;
    }
    let t1;
    if ($[0] !== fieldTab.fields || $[1] !== fieldTab.localized || $[2] !== i18n || $[3] !== locale || $[4] !== parentIsLocalized || $[5] !== selectedLocales || $[6] !== tab || $[7] !== valueFrom || $[8] !== valueTo) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$DiffCollapser$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["DiffCollapser"], {
            fields: fieldTab.fields,
            Label: "label" in tab && tab.label && typeof tab.label !== "function" && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                children: [
                    locale && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                        className: `${baseClass}__locale-label`,
                        children: locale
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(tab.label, i18n)
                ]
            }),
            locales: selectedLocales,
            parentIsLocalized: parentIsLocalized || fieldTab.localized,
            valueFrom,
            valueTo,
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$RenderVersionFieldsToDiff$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["RenderVersionFieldsToDiff"], {
                versionFields: tab.fields
            })
        });
        $[0] = fieldTab.fields;
        $[1] = fieldTab.localized;
        $[2] = i18n;
        $[3] = locale;
        $[4] = parentIsLocalized;
        $[5] = selectedLocales;
        $[6] = tab;
        $[7] = valueFrom;
        $[8] = valueTo;
        $[9] = t1;
    } else {
        t1 = $[9];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/fields/Text/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Text",
    ()=>Text
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'text-diff';
function formatValue(value) {
    if (typeof value === 'string') {
        return {
            tokenizeByCharacter: true,
            value: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(value)
        };
    }
    if (typeof value === 'number') {
        return {
            tokenizeByCharacter: true,
            value: String(value)
        };
    }
    if (typeof value === 'boolean') {
        return {
            tokenizeByCharacter: false,
            value: String(value)
        };
    }
    if (value && typeof value === 'object') {
        return {
            tokenizeByCharacter: false,
            value: `<pre>${(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["escapeDiffHTML"])(JSON.stringify(value, null, 2))}</pre>`
        };
    }
    return {
        tokenizeByCharacter: true,
        value: undefined
    };
}
const Text = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(8);
    const { comparisonValue: valueFrom, field, locale, nestingLevel, versionValue: valueTo } = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let placeholder = "";
    if (valueTo == valueFrom) {
        placeholder = "<span class=\"html-diff-no-value\"><span>";
    }
    let t1;
    if ($[0] !== field.label || $[1] !== i18n || $[2] !== locale || $[3] !== nestingLevel || $[4] !== placeholder || $[5] !== valueFrom || $[6] !== valueTo) {
        const formattedValueFrom = formatValue(valueFrom);
        const formattedValueTo = formatValue(valueTo);
        let tokenizeByCharacter = true;
        if (formattedValueFrom.value?.length) {
            tokenizeByCharacter = formattedValueFrom.tokenizeByCharacter;
        } else {
            if (formattedValueTo.value?.length) {
                tokenizeByCharacter = formattedValueTo.tokenizeByCharacter;
            }
        }
        const renderedValueFrom = formattedValueFrom.value ?? placeholder;
        const renderedValueTo = formattedValueTo.value ?? placeholder;
        const { From, To } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getHTMLDiffComponents"])({
            fromHTML: "<p>" + renderedValueFrom + "</p>",
            postProcess: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["unescapeDiffHTML"],
            toHTML: "<p>" + renderedValueTo + "</p>",
            tokenizeByCharacter
        });
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldDiffContainer"], {
            className: baseClass,
            From,
            i18n,
            label: {
                label: field.label,
                locale
            },
            nestingLevel,
            To
        });
        $[0] = field.label;
        $[1] = i18n;
        $[2] = locale;
        $[3] = nestingLevel;
        $[4] = placeholder;
        $[5] = valueFrom;
        $[6] = valueTo;
        $[7] = t1;
    } else {
        t1 = $[7];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/countChangedFields.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "countChangedFields",
    ()=>countChangedFields,
    "countChangedFieldsInRows",
    ()=>countChangedFieldsInRows
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$fieldHasChanges$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/fieldHasChanges.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/getFieldsForRowComparison.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
function countChangedFields({ config, fields, locales, parentIsLocalized, valueFrom, valueTo }) {
    let count = 0;
    fields.forEach((field)=>{
        // Don't count the id field since it is not displayed in the UI
        if ('name' in field && field.name === 'id') {
            return;
        }
        const fieldType = field.type;
        switch(fieldType){
            // Iterable fields are arrays and blocks fields. We iterate over each row and
            // count the number of changed fields in each.
            case 'array':
            case 'blocks':
                {
                    if (locales && (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldShouldBeLocalized"])({
                        field,
                        parentIsLocalized
                    })) {
                        locales.forEach((locale)=>{
                            const valueFromRows = valueFrom?.[field.name]?.[locale] ?? [];
                            const valueToRows = valueTo?.[field.name]?.[locale] ?? [];
                            count += countChangedFieldsInRows({
                                config,
                                field,
                                locales,
                                parentIsLocalized: parentIsLocalized || field.localized,
                                valueFromRows,
                                valueToRows
                            });
                        });
                    } else {
                        const valueFromRows = valueFrom?.[field.name] ?? [];
                        const valueToRows = valueTo?.[field.name] ?? [];
                        count += countChangedFieldsInRows({
                            config,
                            field,
                            locales,
                            parentIsLocalized: parentIsLocalized || field.localized,
                            valueFromRows,
                            valueToRows
                        });
                    }
                    break;
                }
            // Regular fields without nested fields.
            case 'checkbox':
            case 'code':
            case 'date':
            case 'email':
            case 'join':
            case 'json':
            case 'number':
            case 'point':
            case 'radio':
            case 'relationship':
            case 'richText':
            case 'select':
            case 'text':
            case 'textarea':
            case 'upload':
                {
                    // Fields that have a name and contain data. We can just check if the data has changed.
                    if (locales && (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldShouldBeLocalized"])({
                        field,
                        parentIsLocalized
                    })) {
                        locales.forEach((locale)=>{
                            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$fieldHasChanges$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["fieldHasChanges"])(valueTo?.[field.name]?.[locale], valueFrom?.[field.name]?.[locale])) {
                                count++;
                            }
                        });
                    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$fieldHasChanges$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["fieldHasChanges"])(valueTo?.[field.name], valueFrom?.[field.name])) {
                        count++;
                    }
                    break;
                }
            // Fields that have nested fields, but don't nest their fields' data.
            case 'collapsible':
            case 'row':
                {
                    count += countChangedFields({
                        config,
                        fields: field.fields,
                        locales,
                        parentIsLocalized: parentIsLocalized || field.localized,
                        valueFrom,
                        valueTo
                    });
                    break;
                }
            // Fields that have nested fields and nest their fields' data.
            case 'group':
                {
                    if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["groupHasName"])(field)) {
                        if (locales && (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldShouldBeLocalized"])({
                            field,
                            parentIsLocalized
                        })) {
                            locales.forEach((locale)=>{
                                count += countChangedFields({
                                    config,
                                    fields: field.fields,
                                    locales,
                                    parentIsLocalized: parentIsLocalized || field.localized,
                                    valueFrom: valueFrom?.[field.name]?.[locale],
                                    valueTo: valueTo?.[field.name]?.[locale]
                                });
                            });
                        } else {
                            count += countChangedFields({
                                config,
                                fields: field.fields,
                                locales,
                                parentIsLocalized: parentIsLocalized || field.localized,
                                valueFrom: valueFrom?.[field.name],
                                valueTo: valueTo?.[field.name]
                            });
                        }
                    } else {
                        // Unnamed group field: data is NOT nested under `field.name`
                        count += countChangedFields({
                            config,
                            fields: field.fields,
                            locales,
                            parentIsLocalized: parentIsLocalized || field.localized,
                            valueFrom,
                            valueTo
                        });
                    }
                    break;
                }
            // Each tab in a tabs field has nested fields. The fields data may be
            // nested or not depending on the existence of a name property.
            case 'tabs':
                {
                    field.tabs.forEach((tab)=>{
                        if ('name' in tab && locales && tab.localized) {
                            // Named localized tab
                            locales.forEach((locale)=>{
                                count += countChangedFields({
                                    config,
                                    fields: tab.fields,
                                    locales,
                                    parentIsLocalized: parentIsLocalized || tab.localized,
                                    valueFrom: valueFrom?.[tab.name]?.[locale],
                                    valueTo: valueTo?.[tab.name]?.[locale]
                                });
                            });
                        } else if ('name' in tab) {
                            // Named tab
                            count += countChangedFields({
                                config,
                                fields: tab.fields,
                                locales,
                                parentIsLocalized: parentIsLocalized || tab.localized,
                                valueFrom: valueFrom?.[tab.name],
                                valueTo: valueTo?.[tab.name]
                            });
                        } else {
                            // Unnamed tab
                            count += countChangedFields({
                                config,
                                fields: tab.fields,
                                locales,
                                parentIsLocalized: parentIsLocalized || tab.localized,
                                valueFrom,
                                valueTo
                            });
                        }
                    });
                    break;
                }
            // UI fields don't have data and are not displayed in the version view
            // so we can ignore them.
            case 'ui':
                {
                    break;
                }
            default:
                {
                    const _exhaustiveCheck = fieldType;
                    throw new Error(`Unexpected field.type in countChangedFields : ${String(fieldType)}`);
                }
        }
    });
    return count;
}
function countChangedFieldsInRows({ config, field, locales, parentIsLocalized, valueFromRows = [], valueToRows = [] }) {
    let count = 0;
    let i = 0;
    while(valueFromRows[i] || valueToRows[i]){
        const valueFromRow = valueFromRows?.[i] || {};
        const valueToRow = valueToRows?.[i] || {};
        const { fields: rowFields } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$RenderFieldsToDiff$2f$utilities$2f$getFieldsForRowComparison$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getFieldsForRowComparison"])({
            baseVersionField: {
                type: 'text',
                fields: [],
                path: '',
                schemaPath: ''
            },
            config,
            field,
            row: i,
            valueFromRow,
            valueToRow
        });
        count += countChangedFields({
            config,
            fields: rowFields,
            locales,
            parentIsLocalized: parentIsLocalized || field.localized,
            valueFrom: valueFromRow,
            valueTo: valueToRow
        });
        i++;
    }
    return count;
}
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/fieldHasChanges.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "fieldHasChanges",
    ()=>fieldHasChanges
]);
function fieldHasChanges(a, b) {
    return JSON.stringify(a) !== JSON.stringify(b);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/RenderFieldsToDiff/utilities/getFieldsForRowComparison.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "getFieldsForRowComparison",
    ()=>getFieldsForRowComparison
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
function getFieldsForRowComparison({ baseVersionField, config, field, row, valueFromRow, valueToRow }) {
    let fields = [];
    let versionFields = [];
    if (field.type === 'array' && 'fields' in field) {
        fields = field.fields;
        versionFields = baseVersionField.rows?.length ? baseVersionField.rows[row] : baseVersionField.fields;
    } else if (field.type === 'blocks') {
        if (valueToRow?.blockType === valueFromRow?.blockType) {
            const matchedBlock = config?.blocksMap?.[valueToRow?.blockType] ?? (('blocks' in field || 'blockReferences' in field) && (field.blockReferences ?? field.blocks)?.find((block)=>typeof block !== 'string' && block.slug === valueToRow?.blockType) || {
                fields: []
            });
            fields = matchedBlock.fields;
            versionFields = baseVersionField.rows?.length ? baseVersionField.rows[row] : baseVersionField.fields;
        } else {
            const matchedVersionBlock = config?.blocksMap?.[valueToRow?.blockType] ?? (('blocks' in field || 'blockReferences' in field) && (field.blockReferences ?? field.blocks)?.find((block)=>typeof block !== 'string' && block.slug === valueToRow?.blockType) || {
                fields: []
            });
            const matchedComparisonBlock = config?.blocksMap?.[valueFromRow?.blockType] ?? (('blocks' in field || 'blockReferences' in field) && (field.blockReferences ?? field.blocks)?.find((block)=>typeof block !== 'string' && block.slug === valueFromRow?.blockType) || {
                fields: []
            });
            fields = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getUniqueListBy"])([
                ...matchedVersionBlock.fields,
                ...matchedComparisonBlock.fields
            ], 'name');
            // buildVersionFields already merged the fields of the version and comparison rows together
            versionFields = baseVersionField.rows?.length ? baseVersionField.rows[row] : baseVersionField.fields;
        }
    }
    return {
        fields,
        versionFields
    };
}
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/Restore/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "Restore",
    ()=>Restore
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
;
const baseClass = 'restore-version';
const modalSlug = 'restore-version';
const Restore = ({ className, collectionConfig, globalConfig, label, originalDocID, status, versionDateFormatted, versionID })=>{
    const { config: { routes: { admin: adminRoute, api: apiRoute } } } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { toggleModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRouter"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [draft, setDraft] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useRouteTransition"])();
    const restoreMessage = t(globalConfig ? 'version:aboutToRestoreGlobal' : 'version:aboutToRestore', {
        label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getTranslation"])(label, i18n),
        versionDate: versionDateFormatted
    });
    const canRestoreAsDraft = status !== 'draft' && collectionConfig?.versions?.drafts;
    const handleRestore = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])(async ()=>{
        let fetchURL = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
            apiRoute,
            path: ''
        });
        let redirectURL;
        if (collectionConfig) {
            fetchURL = `${fetchURL}/${collectionConfig.slug}/versions/${versionID}?draft=${draft}`;
            redirectURL = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                adminRoute,
                path: `/collections/${collectionConfig.slug}/${originalDocID}`
            });
        }
        if (globalConfig) {
            fetchURL = `${fetchURL}/globals/${globalConfig.slug}/versions/${versionID}?draft=${draft}`;
            redirectURL = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
                adminRoute,
                path: `/globals/${globalConfig.slug}`
            });
        }
        const res = await __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["requests"].post(fetchURL, {
            headers: {
                'Accept-Language': i18n.language
            }
        });
        if (res.status === 200) {
            const json = await res.json();
            __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].success(json.message);
            return startRouteTransition(()=>router.push(redirectURL));
        } else {
            __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(t('version:problemRestoringVersion'));
        }
    }, [
        apiRoute,
        collectionConfig,
        globalConfig,
        i18n.language,
        versionID,
        draft,
        adminRoute,
        originalDocID,
        startRouteTransition,
        router,
        t
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: [
                    baseClass,
                    className
                ].filter(Boolean).join(' '),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                    buttonStyle: "primary",
                    className: [
                        canRestoreAsDraft && `${baseClass}__restore-as-draft-button`
                    ].filter(Boolean).join(' '),
                    onClick: ()=>toggleModal(modalSlug),
                    size: "xsmall",
                    SubMenuPopupContent: canRestoreAsDraft ? ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PopupList"].ButtonGroup, {
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PopupList"].Button, {
                                onClick: ()=>[
                                        setDraft(true),
                                        toggleModal(modalSlug)
                                    ],
                                children: t('version:restoreAsDraft')
                            })
                        }) : null,
                    children: t('version:restoreThisVersion')
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmationModal"], {
                body: restoreMessage,
                confirmingLabel: t('version:restoring'),
                heading: t('version:confirmVersionRestoration'),
                modalSlug: modalSlug,
                onConfirm: handleRestore
            })
        ]
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectComparison/VersionDrawer/CreatedAtCell.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "VersionDrawerCreatedAtCell",
    ()=>VersionDrawerCreatedAtCell
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const VersionDrawerCreatedAtCell = (t0)=>{
    const { rowData: t1 } = t0;
    const { id, updatedAt } = t1 === undefined ? {} : t1;
    const { config: t2 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t3 } = t2;
    const { dateFormat } = t3;
    const { closeAllModals } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRouter"])();
    const pathname = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["usePathname"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useRouteTransition"])();
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("button", {
        className: "created-at-cell",
        onClick: ()=>{
            closeAllModals();
            const current = new URLSearchParams(Array.from(searchParams.entries()));
            if (id) {
                current.set("versionFrom", String(id));
            }
            const search = current.toString();
            const query = search ? `?${search}` : "";
            startRouteTransition(()=>router.push(`${pathname}${query}`));
        },
        type: "button",
        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatDate"])({
            date: updatedAt,
            i18n,
            pattern: dateFormat
        })
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectComparison/VersionDrawer/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "VersionDrawer",
    ()=>VersionDrawer,
    "VersionDrawerContent",
    ()=>VersionDrawerContent,
    "baseClass",
    ()=>baseClass,
    "formatVersionDrawerSlug",
    ()=>formatVersionDrawerSlug,
    "useVersionDrawer",
    ()=>useVersionDrawer
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const baseClass = 'version-drawer';
const formatVersionDrawerSlug = ({ depth, uuid })=>`version-drawer_${depth}_${uuid}`;
const VersionDrawerContent = (props)=>{
    const { collectionSlug, docID, drawerSlug, globalSlug } = props;
    const { isTrashed } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { closeModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    const prevSearchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(searchParams);
    const { renderDocument } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useServerFunctions"])();
    const [DocumentView, setDocumentView] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(undefined);
    const [isLoading, setIsLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(true);
    const hasRenderedDocument = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(false);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const getDocumentView = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((docID_0)=>{
        const fetchDocumentView = async ()=>{
            setIsLoading(true);
            try {
                const isGlobal = Boolean(globalSlug);
                const entitySlug = collectionSlug ?? globalSlug;
                const result = await renderDocument({
                    collectionSlug: entitySlug,
                    docID: docID_0,
                    drawerSlug,
                    paramsOverride: {
                        segments: [
                            isGlobal ? 'globals' : 'collections',
                            entitySlug,
                            ...isTrashed ? [
                                'trash'
                            ] : [],
                            isGlobal ? undefined : String(docID_0),
                            'versions'
                        ].filter(Boolean)
                    },
                    redirectAfterDelete: false,
                    redirectAfterDuplicate: false,
                    searchParams: Object.fromEntries(searchParams.entries()),
                    versions: {
                        disableGutter: true,
                        useVersionDrawerCreatedAtCell: true
                    }
                });
                if (result?.Document) {
                    setDocumentView(result.Document);
                    setIsLoading(false);
                }
            } catch (error) {
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(error?.message || t('error:unspecific'));
                closeModal(drawerSlug);
            // toast.error(data?.errors?.[0].message || t('error:unspecific'))
            }
        };
        void fetchDocumentView();
    }, [
        closeModal,
        collectionSlug,
        drawerSlug,
        globalSlug,
        isTrashed,
        renderDocument,
        searchParams,
        t
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        if (!hasRenderedDocument.current || prevSearchParams.current !== searchParams) {
            prevSearchParams.current = searchParams;
            getDocumentView(docID);
            hasRenderedDocument.current = true;
        }
    }, [
        docID,
        getDocumentView,
        searchParams
    ]);
    if (isLoading) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["LoadingOverlay"], {});
    }
    return DocumentView;
};
const VersionDrawer = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(6);
    const { collectionSlug, docID, drawerSlug, globalSlug } = props;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t0;
    if ($[0] !== collectionSlug || $[1] !== docID || $[2] !== drawerSlug || $[3] !== globalSlug || $[4] !== t) {
        t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Drawer"], {
            className: baseClass,
            gutter: true,
            slug: drawerSlug,
            title: t("version:selectVersionToCompare"),
            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(VersionDrawerContent, {
                collectionSlug,
                docID,
                drawerSlug,
                globalSlug
            })
        });
        $[0] = collectionSlug;
        $[1] = docID;
        $[2] = drawerSlug;
        $[3] = globalSlug;
        $[4] = t;
        $[5] = t0;
    } else {
        t0 = $[5];
    }
    return t0;
};
const useVersionDrawer = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(29);
    const { collectionSlug, docID, globalSlug } = t0;
    const drawerDepth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useEditDepth"])();
    const uuid = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useId"])();
    const { closeModal, modalState, openModal, toggleModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const [isOpen, setIsOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    let t1;
    if ($[0] !== drawerDepth || $[1] !== uuid) {
        t1 = formatVersionDrawerSlug({
            depth: drawerDepth,
            uuid
        });
        $[0] = drawerDepth;
        $[1] = uuid;
        $[2] = t1;
    } else {
        t1 = $[2];
    }
    const drawerSlug = t1;
    let t2;
    let t3;
    if ($[3] !== drawerSlug || $[4] !== modalState) {
        t2 = ()=>{
            setIsOpen(Boolean(modalState[drawerSlug]?.isOpen));
        };
        t3 = [
            modalState,
            drawerSlug
        ];
        $[3] = drawerSlug;
        $[4] = modalState;
        $[5] = t2;
        $[6] = t3;
    } else {
        t2 = $[5];
        t3 = $[6];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(t2, t3);
    let t4;
    if ($[7] !== drawerSlug || $[8] !== toggleModal) {
        t4 = ()=>{
            toggleModal(drawerSlug);
        };
        $[7] = drawerSlug;
        $[8] = toggleModal;
        $[9] = t4;
    } else {
        t4 = $[9];
    }
    const toggleDrawer = t4;
    let t5;
    if ($[10] !== closeModal || $[11] !== drawerSlug) {
        t5 = ()=>{
            closeModal(drawerSlug);
        };
        $[10] = closeModal;
        $[11] = drawerSlug;
        $[12] = t5;
    } else {
        t5 = $[12];
    }
    const closeDrawer = t5;
    let t6;
    if ($[13] !== drawerSlug || $[14] !== openModal) {
        t6 = ()=>{
            openModal(drawerSlug);
        };
        $[13] = drawerSlug;
        $[14] = openModal;
        $[15] = t6;
    } else {
        t6 = $[15];
    }
    const openDrawer = t6;
    let t7;
    if ($[16] !== collectionSlug || $[17] !== docID || $[18] !== drawerSlug || $[19] !== globalSlug) {
        t7 = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(VersionDrawer, {
                collectionSlug,
                docID,
                drawerSlug,
                globalSlug
            });
        $[16] = collectionSlug;
        $[17] = docID;
        $[18] = drawerSlug;
        $[19] = globalSlug;
        $[20] = t7;
    } else {
        t7 = $[20];
    }
    const MemoizedDrawer = t7;
    let t8;
    if ($[21] !== MemoizedDrawer || $[22] !== closeDrawer || $[23] !== drawerDepth || $[24] !== drawerSlug || $[25] !== isOpen || $[26] !== openDrawer || $[27] !== toggleDrawer) {
        t8 = {
            closeDrawer,
            Drawer: MemoizedDrawer,
            drawerDepth,
            drawerSlug,
            isDrawerOpen: isOpen,
            openDrawer,
            toggleDrawer
        };
        $[21] = MemoizedDrawer;
        $[22] = closeDrawer;
        $[23] = drawerDepth;
        $[24] = drawerSlug;
        $[25] = isOpen;
        $[26] = openDrawer;
        $[27] = toggleDrawer;
        $[28] = t8;
    } else {
        t8 = $[28];
    }
    return t8;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectComparison/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "SelectComparison",
    ()=>SelectComparison
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$VersionDrawer$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectComparison/VersionDrawer/index.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$VersionDrawer$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$VersionDrawer$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'compare-version';
const SelectComparison = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["memo"])((props)=>{
    const { collectionSlug, docID, globalSlug, onChange: onChangeFromProps, versionFromID, versionFromOptions } = props;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { Drawer, openDrawer } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$SelectComparison$2f$VersionDrawer$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useVersionDrawer"])({
        collectionSlug,
        docID,
        globalSlug
    });
    const options = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useMemo"])(()=>{
        return [
            ...versionFromOptions,
            {
                label: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                    className: `${baseClass}-moreVersions`,
                    children: t('version:moreVersions')
                }),
                value: 'more'
            }
        ];
    }, [
        t,
        versionFromOptions
    ]);
    const currentOption = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useMemo"])(()=>versionFromOptions.find((option)=>option.value === versionFromID), [
        versionFromOptions,
        versionFromID
    ]);
    const onChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useCallback"])((val)=>{
        if (val.value === 'more') {
            openDrawer();
            return;
        }
        onChangeFromProps(val);
    }, [
        onChangeFromProps,
        openDrawer
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        className: [
            __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["fieldBaseClass"],
            baseClass
        ].filter(Boolean).join(' '),
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ReactSelect"], {
                isClearable: false,
                isSearchable: false,
                onChange: onChange,
                options: options,
                placeholder: t('version:selectVersionToCompare'),
                value: currentOption
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(Drawer, {})
        ]
    });
});
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/SelectLocales/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "SelectLocales",
    ()=>SelectLocales
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
const baseClass = 'select-version-locales';
const SelectLocales = ({ locales, localeSelectorOpen, onChange })=>{
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["AnimateHeight"], {
        className: baseClass,
        height: localeSelectorOpen ? 'auto' : 0,
        id: `${baseClass}-locales`,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PillSelector"], {
            onClick: ({ pill })=>{
                const newLocales = locales.map((locale)=>{
                    if (locale.name === pill.name) {
                        return {
                            ...locale,
                            selected: !pill.selected
                        };
                    } else {
                        return locale;
                    }
                });
                onChange({
                    locales: newLocales
                });
            },
            pills: locales
        })
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/VersionPillLabel/VersionPillLabel.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "VersionPillLabel",
    ()=>VersionPillLabel
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$getVersionLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/VersionPillLabel/getVersionLabel.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
;
const baseClass = 'version-pill-label';
const renderPill = (label, pillStyle)=>{
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
        pillStyle: pillStyle,
        size: "small",
        children: label
    });
};
const VersionPillLabel = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(14);
    const { currentlyPublishedVersion, disableDate: t1, doc, labelFirst: t2, labelOverride, labelStyle: t3, labelSuffix, latestDraftVersion } = t0;
    const disableDate = t1 === undefined ? false : t1;
    const labelFirst = t2 === undefined ? false : t2;
    const labelStyle = t3 === undefined ? "pill" : t3;
    const { config: t4 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t5, localization } = t4;
    const { dateFormat } = t5;
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { code: currentLocale } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    let t6;
    if ($[0] !== currentLocale || $[1] !== currentlyPublishedVersion || $[2] !== dateFormat || $[3] !== disableDate || $[4] !== doc || $[5] !== i18n || $[6] !== labelFirst || $[7] !== labelOverride || $[8] !== labelStyle || $[9] !== labelSuffix || $[10] !== latestDraftVersion || $[11] !== localization || $[12] !== t) {
        const { label, pillStyle } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$getVersionLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["getVersionLabel"])({
            currentLocale,
            currentlyPublishedVersion,
            latestDraftVersion,
            t,
            version: doc
        });
        const labelText = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("span", {
            children: [
                labelOverride || label,
                labelSuffix
            ]
        });
        const showDate = !disableDate && doc.updatedAt;
        const formattedDate = showDate ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatDate"])({
            date: doc.updatedAt,
            i18n,
            pattern: dateFormat
        }) : null;
        const localeCode = Array.isArray(doc.publishedLocale) ? doc.publishedLocale[0] : doc.publishedLocale;
        const locale = localization && localization?.locales ? localization.locales.find((loc)=>loc.code === localeCode) : null;
        const localeLabel = locale ? locale?.label?.[i18n?.language] || locale?.label : null;
        t6 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: baseClass,
            children: [
                labelFirst ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].Fragment, {
                    children: [
                        labelStyle === "pill" ? renderPill(labelText, pillStyle) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}-text`,
                            children: labelText
                        }),
                        showDate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}-date`,
                            children: formattedDate
                        })
                    ]
                }) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].Fragment, {
                    children: [
                        showDate && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}-date`,
                            children: formattedDate
                        }),
                        labelStyle === "pill" ? renderPill(labelText, pillStyle) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("span", {
                            className: `${baseClass}-text`,
                            children: labelText
                        })
                    ]
                }),
                localeLabel && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
                    size: "small",
                    children: localeLabel
                })
            ]
        });
        $[0] = currentLocale;
        $[1] = currentlyPublishedVersion;
        $[2] = dateFormat;
        $[3] = disableDate;
        $[4] = doc;
        $[5] = i18n;
        $[6] = labelFirst;
        $[7] = labelOverride;
        $[8] = labelStyle;
        $[9] = labelSuffix;
        $[10] = latestDraftVersion;
        $[11] = localization;
        $[12] = t;
        $[13] = t6;
    } else {
        t6 = $[13];
    }
    return t6;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/VersionPillLabel/getVersionLabel.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Gets the appropriate version label and version pill styling
 * given existing versions and the current version status.
 */ __turbopack_context__.s([
    "getVersionLabel",
    ()=>getVersionLabel
]);
function getVersionLabel({ currentLocale, currentlyPublishedVersion, latestDraftVersion, t, version }) {
    const status = version.version._status;
    if (status === 'draft') {
        const publishedNewerThanDraft = currentlyPublishedVersion?.updatedAt > latestDraftVersion?.updatedAt;
        if (publishedNewerThanDraft) {
            return {
                name: 'draft',
                label: t('version:draft'),
                pillStyle: 'light'
            };
        }
        const isCurrentDraft = version.id === latestDraftVersion?.id;
        return {
            name: isCurrentDraft ? 'currentDraft' : 'draft',
            label: isCurrentDraft ? t('version:currentDraft') : t('version:draft'),
            pillStyle: 'light'
        };
    }
    const publishedInAnotherLocale = status === 'published' && version.publishedLocale && currentLocale !== version.publishedLocale;
    if (publishedInAnotherLocale) {
        return {
            name: 'currentDraft',
            label: t('version:currentDraft'),
            pillStyle: 'light'
        };
    }
    const isCurrentlyPublished = currentlyPublishedVersion && version.id === currentlyPublishedVersion.id;
    return {
        name: isCurrentlyPublished ? 'currentlyPublished' : 'previouslyPublished',
        label: isCurrentlyPublished ? t('version:currentlyPublished') : t('version:previouslyPublished'),
        pillStyle: isCurrentlyPublished ? 'success' : 'light'
    };
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Versions/cells/AutosaveCell/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "AutosaveCell",
    ()=>AutosaveCell
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$VersionPillLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Version/VersionPillLabel/VersionPillLabel.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$VersionPillLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$VersionPillLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const baseClass = 'autosave-cell';
const AutosaveCell = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(5);
    const { currentlyPublishedVersion, latestDraftVersion, rowData } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t1;
    if ($[0] !== currentlyPublishedVersion || $[1] !== latestDraftVersion || $[2] !== rowData || $[3] !== t) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: `${baseClass}__items`,
            children: [
                rowData?.autosave && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
                    size: "small",
                    children: t("version:autosave")
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Version$2f$VersionPillLabel$2f$VersionPillLabel$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["VersionPillLabel"], {
                    currentlyPublishedVersion,
                    disableDate: true,
                    doc: rowData,
                    labelFirst: false,
                    labelStyle: "pill",
                    latestDraftVersion
                })
            ]
        });
        $[0] = currentlyPublishedVersion;
        $[1] = latestDraftVersion;
        $[2] = rowData;
        $[3] = t;
        $[4] = t1;
    } else {
        t1 = $[4];
    }
    return t1;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Versions/cells/CreatedAt/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "CreatedAtCell",
    ()=>CreatedAtCell
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-ssr] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const CreatedAtCell = (t0)=>{
    const { collectionSlug, docID, globalSlug, isTrashed, rowData: t1 } = t0;
    const { id, updatedAt } = t1 === undefined ? {} : t1;
    const { config: t2 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t3, routes: t4 } = t2;
    const { dateFormat } = t3;
    const { admin: adminRoute } = t4;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const trashedDocPrefix = isTrashed ? "trash/" : "";
    let to;
    if (collectionSlug) {
        to = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
            adminRoute,
            path: `/collections/${collectionSlug}/${trashedDocPrefix}${docID}/versions/${id}`
        });
    }
    if (globalSlug) {
        to = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
            adminRoute,
            path: `/globals/${globalSlug}/versions/${id}`
        });
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Link"], {
        href: to,
        prefetch: false,
        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["formatDate"])({
            date: updatedAt,
            i18n,
            pattern: dateFormat
        })
    });
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Versions/cells/ID/index.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "IDCell",
    ()=>IDCell
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
'use client';
;
;
function IDCell({ id }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
        children: id
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Versions/index.client.js [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "VersionsViewClient",
    ()=>VersionsViewClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-compiler-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-ssr] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-ssr] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
'use client';
;
;
;
;
;
const VersionsViewClient = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$compiler$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["c"])(13);
    const { baseClass, columns, paginationLimits } = props;
    const { data, handlePageChange, handlePerPageChange } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useListQuery"])();
    const searchParams = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useSearchParams"])();
    let t0;
    if ($[0] !== searchParams) {
        t0 = searchParams.get("limit");
        $[0] = searchParams;
        $[1] = t0;
    } else {
        t0 = $[1];
    }
    const limit = t0;
    const { i18n } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const versionCount = data?.totalDocs || 0;
    const t1 = !data;
    let t2;
    if ($[2] !== baseClass || $[3] !== columns || $[4] !== data || $[5] !== handlePageChange || $[6] !== handlePerPageChange || $[7] !== i18n || $[8] !== limit || $[9] !== paginationLimits || $[10] !== t1 || $[11] !== versionCount) {
        t2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].Fragment, {
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["LoadingOverlayToggle"], {
                    name: "versions",
                    show: t1
                }),
                versionCount === 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: `${baseClass}__no-versions`,
                    children: i18n.t("version:noFurtherVersionsFound")
                }),
                versionCount > 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].Fragment, {
                    children: [
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Table"], {
                            columns,
                            data: data?.docs
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                            className: `${baseClass}__page-controls`,
                            children: [
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pagination"], {
                                    hasNextPage: data.hasNextPage,
                                    hasPrevPage: data.hasPrevPage,
                                    limit: data.limit,
                                    nextPage: data.nextPage,
                                    numberOfNeighbors: 1,
                                    onChange: handlePageChange,
                                    page: data.page,
                                    prevPage: data.prevPage,
                                    totalPages: data.totalPages
                                }),
                                data?.totalDocs > 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["default"].Fragment, {
                                    children: [
                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                            className: `${baseClass}__page-info`,
                                            children: [
                                                data.page * data.limit - (data.limit - 1),
                                                "-",
                                                data.totalPages > 1 && data.totalPages !== data.page ? data.limit * data.page : data.totalDocs,
                                                " ",
                                                i18n.t("general:of"),
                                                " ",
                                                data.totalDocs
                                            ]
                                        }),
                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PerPage"], {
                                            handleChange: handlePerPageChange,
                                            limit: limit ? Number(limit) : 10,
                                            limits: paginationLimits
                                        })
                                    ]
                                })
                            ]
                        })
                    ]
                })
            ]
        });
        $[2] = baseClass;
        $[3] = columns;
        $[4] = data;
        $[5] = handlePageChange;
        $[6] = handlePerPageChange;
        $[7] = i18n;
        $[8] = limit;
        $[9] = paginationLimits;
        $[10] = t1;
        $[11] = versionCount;
        $[12] = t2;
    } else {
        t2 = $[12];
    }
    return t2;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
];

//# sourceMappingURL=0nrf_%40payloadcms_next_dist_1lrfi-b._.js.map