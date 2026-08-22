module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/RenderServerComponent/index.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "RenderServerComponent",
    ()=>RenderServerComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-runtime.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$removeUndefined$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/removeUndefined.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
const RenderServerComponent = ({ clientProps = {}, Component, Fallback, importMap, key, serverProps })=>{
    if (Array.isArray(Component)) {
        return Component.map((c, index)=>RenderServerComponent({
                clientProps,
                Component: c,
                importMap,
                key: index,
                serverProps
            }));
    }
    if (typeof Component === 'function') {
        const isRSC = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["isReactServerComponentOrFunction"])(Component);
        // prevent $undefined from being passed through the rsc requests
        const sanitizedProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$removeUndefined$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["removeUndefined"])({
            ...clientProps,
            ...isRSC ? serverProps : {}
        });
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(Component, {
            ...sanitizedProps
        }, key);
    }
    if (typeof Component === 'string' || (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["isPlainObject"])(Component)) {
        const ResolvedComponent = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getFromImportMap"])({
            importMap,
            PayloadComponent: Component,
            schemaPath: ''
        });
        if (ResolvedComponent) {
            const isRSC = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["isReactServerComponentOrFunction"])(ResolvedComponent);
            // prevent $undefined from being passed through rsc requests
            const sanitizedProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$removeUndefined$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["removeUndefined"])({
                ...clientProps,
                ...isRSC ? serverProps : {},
                ...isRSC && typeof Component === 'object' && Component?.serverProps ? Component.serverProps : {},
                ...typeof Component === 'object' && Component?.clientProps ? Component.clientProps : {}
            });
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(ResolvedComponent, {
                ...sanitizedProps
            }, key);
        }
    }
    return Fallback ? RenderServerComponent({
        clientProps,
        Component: Fallback,
        importMap,
        key,
        serverProps
    }) : null;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "EntityType",
    ()=>x,
    "PayloadIcon",
    ()=>te,
    "PayloadLogo",
    ()=>oe,
    "Translation",
    ()=>B,
    "WithServerSideProps",
    ()=>Y,
    "abortAndIgnore",
    ()=>le,
    "filterFields",
    ()=>v,
    "findLocaleFromCode",
    ()=>fe,
    "formatDate",
    ()=>M,
    "formatDocTitle",
    ()=>ye,
    "getGlobalData",
    ()=>xe,
    "getInitialColumns",
    ()=>ie,
    "getNavGroups",
    ()=>De,
    "getVisibleEntities",
    ()=>be,
    "groupNavItems",
    ()=>F,
    "handleAbortRef",
    ()=>ae,
    "handleBackToDashboard",
    ()=>ve,
    "handleGoBack",
    ()=>Ce,
    "handleTakeOver",
    ()=>Me,
    "hasSavePermission",
    ()=>Se,
    "isClientUserObject",
    ()=>Le,
    "isEditing",
    ()=>Fe,
    "mergeFieldStyles",
    ()=>q,
    "reduceToSerializableFields",
    ()=>X,
    "requests",
    ()=>ce,
    "sanitizeID",
    ()=>ke,
    "traverseForLocalizedFields",
    ()=>D,
    "withMergedProps",
    ()=>_
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-runtime.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$stringify$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/stringify.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$format$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/format.js [app-route] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$transpose$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/transpose.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
var U = ({ elements: e, translationString: t })=>{
    let r = /(<[^>]+>.*?<\/[^>]+>)/g, o = t.split(r);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("span", {
        children: o.map((n, s)=>{
            if (e && n.startsWith("<") && n.endsWith(">")) {
                let i = n[1], l = e[i];
                if (l) {
                    let a = new RegExp(`<${i}>(.*?)</${i}>`, "g"), p = n.replace(a, (c, f)=>f);
                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(l, {
                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(U, {
                            translationString: p
                        })
                    }, s);
                }
            }
            return n;
        })
    });
}, B = ({ elements: e, i18nKey: t, t: r, variables: o })=>{
    let n = r(t, o || {});
    return e ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(U, {
        elements: e,
        translationString: n
    }) : n;
};
;
;
;
function _({ Component: e, sanitizeServerOnlyProps: t, toMergeIntoProps: r }) {
    return t === void 0 && (t = !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["isReactServerComponentOrFunction"])(e)), (n)=>{
        let s = W(n, r);
        return t && __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["serverProps"].forEach((i)=>{
            delete s[i];
        }), (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(e, {
            ...s
        });
    };
}
function W(e, t) {
    return {
        ...e,
        ...t
    };
}
;
;
;
var Y = ({ Component: e, serverOnlyProps: t, ...r })=>e ? ((n)=>{
        let s = {
            ...n,
            ...(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["isReactServerComponentOrFunction"])(e) ? t ?? {} : {}
        };
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])(e, {
            ...s
        });
    })(r) : null;
var q = (e)=>({
        ...e?.admin?.style || {},
        ...e?.admin?.width ? {
            "--field-width": e.admin.width
        } : {
            flex: "1 1 auto"
        },
        ...e?.admin?.style?.flex ? {
            flex: e.admin.style.flex
        } : {}
    });
var Q = [
    "validate",
    "customComponents"
], J = (e)=>{
    let t = {
        ...e
    };
    for (let r of Q)delete t[r];
    return t;
}, X = (e)=>{
    let t = {};
    for(let r in e)t[r] = J(e[r]);
    return t;
};
;
;
var te = ({ fill: e })=>{
    let t = e || "var(--theme-elevation-1000)";
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxs"])("svg", {
        className: "graphic-icon",
        height: "100%",
        viewBox: "0 0 25 25",
        width: "100%",
        xmlns: "http://www.w3.org/2000/svg",
        children: [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                d: "M11.8673 21.2336L4.40922 16.9845C4.31871 16.9309 4.25837 16.8355 4.25837 16.7282V10.1609C4.25837 10.0477 4.38508 9.97616 4.48162 10.0298L13.1404 14.9642C13.2611 15.0358 13.412 14.9464 13.412 14.8093V11.6091C13.412 11.4839 13.3456 11.3647 13.2309 11.2992L2.81624 5.36353C2.72573 5.30989 2.60505 5.30989 2.51454 5.36353L1.15085 6.14422C1.06034 6.19786 1 6.29321 1 6.40048V18.5995C1 18.7068 1.06034 18.8021 1.15085 18.8558L11.8491 24.9583C11.9397 25.0119 12.0603 25.0119 12.1509 24.9583L21.1355 19.8331C21.2562 19.7616 21.2562 19.5948 21.1355 19.5232L18.3357 17.9261C18.2211 17.8605 18.0883 17.8605 17.9737 17.9261L12.175 21.2336C12.0845 21.2872 11.9638 21.2872 11.8733 21.2336H11.8673Z",
                fill: t
            }),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                d: "M22.8491 6.13827L12.1508 0.0417218C12.0603 -0.0119135 11.9397 -0.0119135 11.8491 0.0417218L6.19528 3.2658C6.0746 3.33731 6.0746 3.50418 6.19528 3.57569L8.97092 5.16091C9.08557 5.22647 9.21832 5.22647 9.33296 5.16091L11.8672 3.71872C11.9578 3.66508 12.0784 3.66508 12.1689 3.71872L19.627 7.96782C19.7175 8.02146 19.7778 8.11681 19.7778 8.22408V14.8212C19.7778 14.9464 19.8442 15.0656 19.9589 15.1311L22.7345 16.7104C22.8552 16.7819 23.006 16.6925 23.006 16.5554V6.40048C23.006 6.29321 22.9457 6.19786 22.8552 6.14423L22.8491 6.13827Z",
                fill: t
            })
        ]
    });
};
;
;
var re = `
  .graphic-logo path {
    fill: var(--theme-elevation-1000);
  }
`, oe = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxs"])("svg", {
        className: "graphic-logo",
        fill: "none",
        height: "43.5",
        id: "b",
        viewBox: "0 0 193.38 43.5",
        width: "193.38",
        xmlns: "http://www.w3.org/2000/svg",
        children: [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("style", {
                children: re
            }),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxs"])("g", {
                id: "c",
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                        d: "M18.01,35.63l-12.36-7.13c-.15-.09-.25-.25-.25-.43v-11.02c0-.19.21-.31.37-.22l14.35,8.28c.2.12.45-.03.45-.26v-5.37c0-.21-.11-.41-.3-.52L3.01,9c-.15-.09-.35-.09-.5,0l-2.26,1.31c-.15.09-.25.25-.25.43v20.47c0,.18.1.34.25.43l17.73,10.24c.15.09.35.09.5,0l14.89-8.6c.2-.12.2-.4,0-.52l-4.64-2.68c-.19-.11-.41-.11-.6,0l-9.61,5.55c-.15.09-.35.09-.5,0Z"
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                        d: "M36.21,10.3L18.48.07c-.15-.09-.35-.09-.5,0l-9.37,5.41c-.2.12-.2.4,0,.52l4.6,2.66c.19.11.41.11.6,0l4.2-2.42c.15-.09.35-.09.5,0l12.36,7.13c.15.09.25.25.25.43v11.07c0,.21.11.41.3.52l4.6,2.65c.2.12.45-.03.45-.26V10.74c0-.18-.1-.34-.25-.43Z"
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsxs"])("g", {
                        id: "d",
                        children: [
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M193.38,9.47c0,1.94-1.48,3.32-3.3,3.32s-3.31-1.39-3.31-3.32,1.49-3.31,3.31-3.31,3.3,1.39,3.3,3.31ZM192.92,9.47c0-1.68-1.26-2.88-2.84-2.88s-2.84,1.2-2.84,2.88,1.26,2.89,2.84,2.89,2.84-1.2,2.84-2.89ZM188.69,11.17v-3.51h1.61c.85,0,1.35.39,1.35,1.15,0,.53-.3.86-.67,1.02l.79,1.35h-.89l-.72-1.22h-.64v1.22h-.82ZM190.18,9.31c.46,0,.64-.16.64-.5s-.19-.49-.64-.49h-.67v.99h.67Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M54.72,24.84v10.93h-5.4V6.1h12.26c7.02,0,11.1,3.2,11.1,9.39s-4.07,9.35-11.06,9.35h-6.9,0ZM61.12,20.52c4.07,0,6.11-1.66,6.11-5.03s-2.04-5.03-6.11-5.03h-6.4v10.06h6.4Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M85.94,32.45c-1,2.41-3.66,3.78-7.02,3.78-4.11,0-7.11-2.29-7.11-6.11,0-4.24,3.32-5.98,7.61-6.48l6.32-.71v-1c0-2.58-1.58-3.82-3.99-3.82s-3.74,1.29-3.91,3.24h-5.11c.46-4.53,3.99-7.19,9.18-7.19,5.74,0,9.02,2.7,9.02,8.19v8.15c0,1.95.08,3.58.42,5.28h-5.11c-.21-1.16-.29-2.29-.29-3.32h0ZM85.73,27.58v-1.29l-4.7.54c-2.24.29-3.95.79-3.95,2.99,0,1.66,1.16,2.7,3.28,2.7,2.74,0,5.36-1.62,5.36-4.95h0Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M90.39,14.66h5.4l5.86,15.92h.08l5.57-15.92h5.28l-8.23,21.49c-2,5.28-4.45,7.32-8.89,7.36-.71,0-1.7-.08-2.45-.21v-4.03c.62.13.96.13,1.41.13,2.16,0,3.07-.75,4.2-3.66l-8.23-21.07h0Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M113.46,35.77V6.1h5.32v29.67h-5.32Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M130.79,36.27c-6.23,0-10.68-4.2-10.68-11.05s4.45-11.05,10.68-11.05,10.68,4.24,10.68,11.05-4.45,11.05-10.68,11.05ZM130.79,32.32c3.41,0,5.36-2.66,5.36-7.11s-1.95-7.11-5.36-7.11-5.36,2.7-5.36,7.11,1.91,7.11,5.36,7.11Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M156.19,32.45c-1,2.41-3.66,3.78-7.02,3.78-4.11,0-7.11-2.29-7.11-6.11,0-4.24,3.32-5.98,7.61-6.48l6.32-.71v-1c0-2.58-1.58-3.82-3.99-3.82s-3.74,1.29-3.91,3.24h-5.11c.46-4.53,3.99-7.19,9.19-7.19,5.74,0,9.02,2.7,9.02,8.19v8.15c0,1.95.08,3.58.42,5.28h-5.11c-.21-1.16-.29-2.29-.29-3.32h0ZM155.98,27.58v-1.29l-4.7.54c-2.24.29-3.95.79-3.95,2.99,0,1.66,1.16,2.7,3.28,2.7,2.74,0,5.36-1.62,5.36-4.95h0Z"
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$runtime$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["jsx"])("path", {
                                d: "M178.5,32.41c-1.04,2.12-3.58,3.87-6.78,3.87-5.53,0-9.31-4.49-9.31-11.05s3.78-11.05,9.31-11.05c3.28,0,5.69,1.83,6.69,3.95V6.1h5.32v29.67h-5.24v-3.37h0ZM178.55,24.84c0-4.11-1.95-6.78-5.32-6.78s-5.45,2.83-5.45,7.15,2,7.15,5.45,7.15,5.32-2.66,5.32-6.78v-.75h0Z"
                            })
                        ]
                    })
                ]
            })
        ]
    });
;
var v = (e)=>{
    let t = (r)=>r.type !== "ui" && (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsHiddenOrDisabled"])(r) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsID"])(r) || r?.admin?.disableListColumn === !0;
    return (e ?? []).reduce((r, o)=>{
        if (t(o)) return r;
        if (o.type === "tabs" && "tabs" in o) {
            let n = {
                ...o,
                tabs: o.tabs.map((s)=>({
                        ...s,
                        fields: v(s.fields)
                    }))
            };
            return r.push(n), r;
        }
        if ("fields" in o && Array.isArray(o.fields)) {
            let n = {
                ...o,
                fields: v(o.fields)
            };
            return r.push(n), r;
        }
        return r.push(o), r;
    }, []);
};
;
var w = (e, t)=>e?.reduce((r, o)=>(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(o) && o.name === t ? r : !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(o) && "fields" in o ? [
            ...r,
            ...w(o.fields, t)
        ] : o.type === "tabs" && "tabs" in o ? [
            ...r,
            ...o.tabs.reduce((n, s)=>[
                    ...n,
                    ..."name" in s ? [
                        s.name
                    ] : w(s.fields, t)
                ], [])
        ] : [
            ...r,
            o.name
        ], []), ie = (e, t, r)=>{
    let o = [];
    if (Array.isArray(r) && r.length >= 1) o = r;
    else {
        t && o.push(t);
        let n = w(e, t);
        o = o.concat(n), o = o.slice(0, 4);
    }
    return o.map((n)=>({
            accessor: n,
            active: !0
        }));
};
function le(e) {
    if (e) try {
        e.abort();
    } catch  {}
}
function ae(e) {
    let t = new AbortController;
    if (e.current) try {
        e.current.abort();
    } catch  {}
    return e.current = t, t;
}
;
var ce = {
    delete: (e, t = {
        headers: {}
    })=>{
        let r = t && t.headers ? {
            ...t.headers
        } : {}, o = {
            ...t,
            credentials: "include",
            headers: {
                ...r
            },
            method: "delete"
        };
        return fetch(e, o);
    },
    get: (e, t = {
        headers: {}
    })=>{
        let r = "";
        return t.params && (r = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$stringify$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["stringify"](t.params, {
            addQueryPrefix: !0
        })), fetch(`${e}${r}`, {
            credentials: "include",
            ...t
        });
    },
    patch: (e, t = {
        headers: {}
    })=>{
        let r = t && t.headers ? {
            ...t.headers
        } : {}, o = {
            ...t,
            credentials: "include",
            headers: {
                ...r
            },
            method: "PATCH"
        };
        return fetch(e, o);
    },
    post: (e, t = {
        headers: {}
    })=>{
        let r = t && t.headers ? {
            ...t.headers
        } : {}, o = {
            ...t,
            credentials: "include",
            headers: {
                ...r
            },
            method: "post"
        };
        return fetch(`${e}`, o);
    },
    put: (e, t = {
        headers: {}
    })=>{
        let r = t && t.headers ? {
            ...t.headers
        } : {}, o = {
            ...t,
            credentials: "include",
            headers: {
                ...r
            },
            method: "put"
        };
        return fetch(e, o);
    }
};
var fe = (e, t)=>!e?.locales || e.locales.length === 0 ? null : e.locales.find((r)=>r?.code === t);
;
var pe = {}, h = {};
function d(e, t) {
    try {
        let o = (pe[e] ||= new Intl.DateTimeFormat("en-GB", {
            timeZone: e,
            hour: "numeric",
            timeZoneName: "longOffset"
        }).format)(t).split("GMT")[1] || "";
        return o in h ? h[o] : N(o, o.split(":"));
    } catch  {
        if (e in h) return h[e];
        let r = e?.match(me);
        return r ? N(e, r.slice(1)) : NaN;
    }
}
var me = /([+-]\d\d):?(\d\d)?/;
function N(e, t) {
    let r = +t[0], o = +(t[1] || 0);
    return h[e] = r > 0 ? r * 60 + o : r * 60 - o;
}
var m = class e extends Date {
    constructor(...t){
        super(), t.length > 1 && typeof t[t.length - 1] == "string" && (this.timeZone = t.pop()), this.internal = new Date, isNaN(d(this.timeZone, this)) ? this.setTime(NaN) : t.length ? typeof t[0] == "number" && (t.length === 1 || t.length === 2 && typeof t[1] != "number") ? this.setTime(t[0]) : typeof t[0] == "string" ? this.setTime(+new Date(t[0])) : t[0] instanceof Date ? this.setTime(+t[0]) : (this.setTime(+new Date(...t)), P(this, NaN), C(this)) : this.setTime(Date.now());
    }
    static tz(t, ...r) {
        return r.length ? new e(...r, t) : new e(Date.now(), t);
    }
    withTimeZone(t) {
        return new e(+this, t);
    }
    getTimezoneOffset() {
        return -d(this.timeZone, this);
    }
    setTime(t) {
        return Date.prototype.setTime.apply(this, arguments), C(this), +this;
    }
    [Symbol.for("constructDateFrom")](t) {
        return new e(+new Date(t), this.timeZone);
    }
}, A = /^(get|set)(?!UTC)/;
Object.getOwnPropertyNames(Date.prototype).forEach((e)=>{
    if (!A.test(e)) return;
    let t = e.replace(A, "$1UTC");
    m.prototype[t] && (e.startsWith("get") ? m.prototype[e] = function() {
        return this.internal[t]();
    } : (m.prototype[e] = function() {
        return Date.prototype[t].apply(this.internal, arguments), de(this), +this;
    }, m.prototype[t] = function() {
        return Date.prototype[t].apply(this, arguments), C(this), +this;
    }));
});
function C(e) {
    e.internal.setTime(+e), e.internal.setUTCMinutes(e.internal.getUTCMinutes() - e.getTimezoneOffset());
}
function de(e) {
    Date.prototype.setFullYear.call(e, e.internal.getUTCFullYear(), e.internal.getUTCMonth(), e.internal.getUTCDate()), Date.prototype.setHours.call(e, e.internal.getUTCHours(), e.internal.getUTCMinutes(), e.internal.getUTCSeconds(), e.internal.getUTCMilliseconds()), P(e);
}
function P(e) {
    let t = d(e.timeZone, e), r = new Date(+e);
    r.setUTCHours(r.getUTCHours() - 1);
    let o = -new Date(+e).getTimezoneOffset(), n = -new Date(+r).getTimezoneOffset(), s = o - n, i = Date.prototype.getHours.apply(e) !== e.internal.getUTCHours();
    s && i && e.internal.setUTCMinutes(e.internal.getUTCMinutes() + s);
    let l = o - t;
    l && Date.prototype.setUTCMinutes.call(e, Date.prototype.getUTCMinutes.call(e) + l);
    let a = d(e.timeZone, e), c = -new Date(+e).getTimezoneOffset() - a, f = a !== t, k = c - l;
    if (f && k) {
        Date.prototype.setUTCMinutes.call(e, Date.prototype.getUTCMinutes.call(e) + k);
        let I = d(e.timeZone, e), b = a - I;
        b && (e.internal.setUTCMinutes(e.internal.getUTCMinutes() + b), Date.prototype.setUTCMinutes.call(e, Date.prototype.getUTCMinutes.call(e) + b));
    }
}
;
var M = ({ date: e, i18n: t, pattern: r, timezone: o })=>{
    let n = new m(new Date(e));
    if (o) {
        let s = m.tz(o), i = n.withTimeZone(o), l = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$transpose$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["transpose"])(i, s);
        return t.dateFNS ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$format$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["format"])(l, r, {
            locale: t.dateFNS
        }) : `${t.t("general:loading")}...`;
    }
    return t.dateFNS ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$format$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__$3c$locals$3e$__["format"])(n, r, {
        locale: t.dateFNS
    }) : `${t.t("general:loading")}...`;
};
;
function S(e) {
    return typeof e == "object" && "root" in e;
}
function y(e, t) {
    for (let r of e)"text" in r && r.text ? t += r.text : "children" in r || (t += `[${r.type}]`), "children" in r && r.children && (t += y(r.children, t));
    return t;
}
var z = (e)=>Array.isArray(e) ? e.map((t)=>typeof t == "object" && t !== null ? t.id : String(t)).filter(Boolean).join(", ") : typeof e == "object" && e !== null ? e.id || "" : String(e);
var ye = ({ collectionConfig: e, data: t, dateFormat: r, fallback: o, globalConfig: n, i18n: s })=>{
    let i;
    if (e) {
        let l = e?.admin?.useAsTitle;
        if (l && (i = t?.[l], i)) {
            let a = e.fields.find((f)=>"name" in f && f.name === l), p = a?.type === "date", c = a?.type === "relationship";
            if (p) {
                let f = "date" in a.admin && a?.admin?.date?.displayFormat || r;
                i = M({
                    date: i,
                    i18n: s,
                    pattern: f
                }) || i;
            }
            c && (i = z(t[l]));
        }
    }
    return n && (i = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getTranslation"])(n?.label, s) || n?.slug), i && S(i) && (i = y(i.root.children?.[0]?.children || [], "")), !i && S(o) && (i = y(o.root.children?.[0]?.children || [], "")), i || (i = typeof o == "string" ? o : `[${s.t("general:untitled")}]`), i;
};
async function xe(e) {
    let { payload: { config: t }, payload: r } = e, o = [];
    if (t.globals.length > 0) if (r.collections?.["payload-locked-documents"]) {
        let n = await r.find({
            collection: "payload-locked-documents",
            depth: 1,
            overrideAccess: !1,
            pagination: !1,
            req: e,
            select: {
                globalSlug: !0,
                updatedAt: !0,
                user: !0
            },
            where: {
                globalSlug: {
                    exists: !0
                }
            }
        });
        o = t.globals.map((s)=>{
            let i = typeof s.lockDocuments == "object" ? s.lockDocuments.duration : 300, l = n.docs.find((a)=>a.globalSlug === s.slug);
            return {
                slug: s.slug,
                data: {
                    _isLocked: !!l,
                    _lastEditedAt: l?.updatedAt ?? null,
                    _userEditing: l?.user?.value ?? null
                },
                lockDuration: i
            };
        });
    } else o = t.globals.map((n)=>{
        let s = typeof n.lockDocuments == "object" ? n.lockDocuments.duration : 300;
        return {
            slug: n.slug,
            data: {
                _isLocked: !1,
                _lastEditedAt: null,
                _userEditing: null
            },
            lockDuration: s
        };
    });
    return o;
}
;
var x = function(e) {
    return e.collection = "collections", e.global = "globals", e;
}({});
function F(e, t, r) {
    return e.reduce((n, s)=>{
        if (s.entity?.admin?.group === !1) return n;
        if (t?.[s.type.toLowerCase()]?.[s.entity.slug]?.read) {
            let i = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getTranslation"])(s.entity.admin.group, r), l = "labels" in s.entity ? s.entity.labels.plural : s.entity.label, a = typeof l == "function" ? l({
                i18n: r,
                t: r.t
            }) : l;
            if (s.entity.admin.group) {
                let p = n.find((f)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getTranslation"])(f.label, r) === i), c = p;
                p || (c = {
                    entities: [],
                    label: i
                }, n.push(c)), c.entities.push({
                    slug: s.entity.slug,
                    type: s.type,
                    label: a
                });
            } else n.find((c)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["getTranslation"])(c.label, r) === r.t(`general:${s.type}`)).entities.push({
                slug: s.entity.slug,
                type: s.type,
                label: a
            });
        }
        return n;
    }, [
        {
            entities: [],
            label: r.t("general:collections")
        },
        {
            entities: [],
            label: r.t("general:globals")
        }
    ]).filter((n)=>n.entities.length > 0);
}
function De(e, t, r, o) {
    let n = r.collections.filter((l)=>e?.collections?.[l.slug]?.read && t.collections.includes(l.slug)), s = r.globals.filter((l)=>e?.globals?.[l.slug]?.read && t.globals.includes(l.slug));
    return F([
        ...n.map((l)=>({
                type: x.collection,
                entity: l
            })) ?? [],
        ...s.map((l)=>({
                type: x.global,
                entity: l
            })) ?? []
    ], e, o);
}
function E(e, t) {
    if (typeof e == "function") try {
        return e({
            user: t
        });
    } catch  {
        return !0;
    }
    return !!e;
}
function be({ req: e }) {
    return {
        collections: e.payload.config.collections.map(({ slug: t, admin: { hidden: r } })=>E(r, e.user) ? null : t).filter(Boolean),
        globals: e.payload.config.globals.map(({ slug: t, admin: { hidden: r } })=>E(r, e.user) ? null : t).filter(Boolean)
    };
}
;
var ve = ({ adminRoute: e, router: t, serverURL: r })=>{
    let o = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
        adminRoute: e,
        path: "",
        serverURL: r
    });
    t.push(o);
};
;
var Ce = ({ adminRoute: e, collectionSlug: t, router: r, serverURL: o })=>{
    let n = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["formatAdminURL"])({
        adminRoute: e,
        path: t ? `/collections/${t}` : "/"
    });
    r.push(n);
};
var Me = async ({ id: e, clearRouteCache: t, collectionSlug: r, documentLockStateRef: o, globalSlug: n, isLockingEnabled: s, isWithinDoc: i, setCurrentEditor: l, setIsReadOnlyForIncomingUser: a, updateDocumentEditor: p, user: c })=>{
    if (s) try {
        await p(e, r ?? n, c), i || (o.current.hasShownLockedModal = !0), o.current = {
            hasShownLockedModal: o.current?.hasShownLockedModal,
            isLocked: !0,
            user: c
        }, l(c), i && a && a(!1), t && t();
    } catch (f) {
        console.error("Error during document takeover:", f);
    }
};
var Se = (e)=>{
    let { collectionSlug: t, docPermissions: r, globalSlug: o, isEditing: n } = e;
    return t ? !!(n && r?.update || !n && r?.create) : o ? !!r?.update : !1;
};
var Le = (e)=>e && typeof e == "object";
var Fe = ({ id: e, collectionSlug: t, globalSlug: r })=>!!(r || t && e);
function ke(e) {
    return e === void 0 || typeof e == "number" ? e : decodeURIComponent(e);
}
var D = (e)=>{
    for (let t of e){
        if ("localized" in t && t.localized) return !0;
        switch(t.type){
            case "array":
            case "collapsible":
            case "group":
            case "row":
                if (t.fields && D(t.fields)) return !0;
                break;
            case "blocks":
                if (t.blocks) {
                    for (let r of t.blocks)if (r.fields && D(r.fields)) return !0;
                }
                break;
            case "tabs":
                if (t.tabs) {
                    for (let r of t.tabs)if ("localized" in r && r.localized || "fields" in r && r.fields && D(r.fields)) return !0;
                }
                break;
        }
    }
    return !1;
};
;
;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/addFieldStatePromise.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "addFieldStatePromise",
    ()=>addFieldStatePromise
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$resolveFilterOptions$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/resolveFilterOptions.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/isRowCollapsed.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
const ObjectId = 'default' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["default"] ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["default"].default : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["default"];
const addFieldStatePromise = async (args)=>{
    const { id, addErrorPathToParent: addErrorPathToParentArg, anyParentLocalized = false, blockData, clientFieldSchemaMap, collectionSlug, data, field, fieldSchemaMap, filter, forceFullValue = false, fullData, includeSchema = false, indexPath, mockRSCs, omitParents = false, operation, parentPath, parentPermissions, parentSchemaPath, passesCondition, path, preferences, previousFormState, readOnly, renderAllFields, renderFieldFn, req, schemaPath, select, selectMode, skipConditionChecks = false, skipValidation = false, state } = args;
    if (!args.clientFieldSchemaMap && args.renderFieldFn) {
        // eslint-disable-next-line no-console
        console.warn('clientFieldSchemaMap is not passed to addFieldStatePromise - this will reduce performance');
    }
    let fieldPermissions = true;
    const fieldState = {};
    const lastRenderedPath = previousFormState?.[path]?.lastRenderedPath;
    // Append only if true to avoid sending '$undefined' through the network
    if (lastRenderedPath) {
        fieldState.lastRenderedPath = lastRenderedPath;
    }
    // If we're rendering all fields, no need to flag this as added by server
    const addedByServer = !renderAllFields && !previousFormState?.[path];
    // Append only if true to avoid sending '$undefined' through the network
    if (addedByServer) {
        fieldState.addedByServer = true;
    }
    // Append only if true to avoid sending '$undefined' through the network
    if (passesCondition === false) {
        fieldState.passesCondition = false;
    }
    // Append only if true to avoid sending '$undefined' through the network
    if (includeSchema) {
        fieldState.fieldSchema = field;
    }
    // Short-circuit hidden fields to prevent recursing and rendering. Two exclusions:
    // - `tab`: visibility is keyed by `field.id` (not `path`); the tab branch owns that write.
    // - presentational containers (row, collapsible, unnamed group): they hold no value, so
    //   returning here drops their nested fields' values. They fall through to the
    //   `fieldHasSubFields` branch, which recurses to preserve child values without rendering.
    const isPresentationalWithSubFields = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldHasSubFields"])(field) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field);
    if (passesCondition === false && field.type !== 'tab' && !isPresentationalWithSubFields) {
        if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field) && data?.[field.name] !== undefined) {
            fieldState.value = data[field.name];
            fieldState.initialValue = data[field.name];
        }
        if (!filter || filter(args)) {
            state[path] = fieldState;
        }
        return;
    }
    if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsHiddenOrDisabled"])(field) && field.type !== 'tab') {
        fieldPermissions = parentPermissions === true ? parentPermissions : (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["deepCopyObjectSimple"])(parentPermissions?.[field.name]);
        let hasPermission = fieldPermissions === true || (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["deepCopyObjectSimple"])(fieldPermissions?.read);
        if (typeof field?.access?.read === 'function') {
            hasPermission = await field.access.read({
                id,
                blockData,
                data: fullData,
                req,
                siblingData: data
            });
        } else {
            hasPermission = true;
        }
        if (!hasPermission) {
            return;
        }
        const validate = 'validate' in field ? field.validate : undefined;
        let validationResult = true;
        if (typeof validate === 'function' && !skipValidation && passesCondition) {
            let jsonError;
            if (field.type === 'json' && typeof data[field.name] === 'string') {
                try {
                    JSON.parse(data[field.name]);
                } catch (e) {
                    jsonError = e;
                }
            }
            try {
                validationResult = await validate(data?.[field.name], {
                    ...field,
                    id,
                    blockData,
                    collectionSlug,
                    data: fullData,
                    event: 'onChange',
                    // @AlessioGr added `jsonError` in https://github.com/payloadcms/payload/commit/c7ea62a39473408c3ea912c4fbf73e11be4b538d
                    // @ts-expect-error-next-line
                    jsonError,
                    operation,
                    preferences,
                    previousValue: previousFormState?.[path]?.initialValue,
                    req,
                    siblingData: data
                });
            } catch (err) {
                validationResult = `Error validating field at path: ${path}`;
                req.payload.logger.error({
                    err,
                    msg: validationResult
                });
            }
        }
        /**
    * This function adds the error **path** to the current field and all its parents. If a field is invalid, all its parents are also invalid.
    * It does not add the error **message** to the current field, as that shouldn't apply to all parents.
    * This is done separately below.
    */ const addErrorPathToParent = (errorPath)=>{
            if (typeof addErrorPathToParentArg === 'function') {
                addErrorPathToParentArg(errorPath);
            }
            if (!fieldState.errorPaths) {
                fieldState.errorPaths = [];
            }
            if (!fieldState.errorPaths.includes(errorPath)) {
                fieldState.errorPaths.push(errorPath);
                fieldState.valid = false;
            }
        };
        if (typeof validationResult === 'string') {
            fieldState.errorMessage = validationResult;
            fieldState.valid = false;
            addErrorPathToParent(path);
        }
        switch(field.type){
            case 'array':
                {
                    const arrayValue = Array.isArray(data[field.name]) ? data[field.name] : [];
                    const arraySelect = select?.[field.name];
                    const { promises, rows } = arrayValue.reduce((acc, row, rowIndex)=>{
                        const rowPath = path + '.' + rowIndex;
                        row.id = row?.id || new ObjectId().toHexString();
                        if (!omitParents && (!filter || filter(args))) {
                            const idKey = rowPath + '.id';
                            state[idKey] = {
                                initialValue: row.id,
                                value: row.id
                            };
                            if (includeSchema) {
                                state[idKey].fieldSchema = field.fields.find((field)=>(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsID"])(field));
                            }
                        }
                        acc.promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                            id,
                            addErrorPathToParent,
                            anyParentLocalized: field.localized || anyParentLocalized,
                            blockData,
                            clientFieldSchemaMap,
                            collectionSlug,
                            data: row,
                            fields: field.fields,
                            fieldSchemaMap,
                            filter,
                            forceFullValue,
                            fullData,
                            includeSchema,
                            mockRSCs,
                            omitParents,
                            operation,
                            parentIndexPath: '',
                            parentPassesCondition: passesCondition,
                            parentPath: rowPath,
                            parentSchemaPath: schemaPath,
                            permissions: fieldPermissions === true ? fieldPermissions : fieldPermissions?.fields || {},
                            preferences,
                            previousFormState,
                            readOnly,
                            renderAllFields,
                            renderFieldFn,
                            req,
                            select: typeof arraySelect === 'object' ? arraySelect : undefined,
                            selectMode,
                            skipConditionChecks,
                            skipValidation,
                            state
                        }));
                        if (!acc.rows) {
                            acc.rows = [];
                        }
                        // First, check if `previousFormState` has a matching row
                        const previousRow = (previousFormState?.[path]?.rows || []).find((prevRow)=>prevRow.id === row.id);
                        const newRow = {
                            id: row.id,
                            isLoading: false
                        };
                        if (previousRow?.lastRenderedPath) {
                            newRow.lastRenderedPath = previousRow.lastRenderedPath;
                        }
                        // add addedByServer flag
                        if (!previousRow) {
                            newRow.addedByServer = true;
                        }
                        const isCollapsed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["isRowCollapsed"])({
                            collapsedPrefs: preferences?.fields?.[path]?.collapsed,
                            field,
                            previousRow,
                            row
                        });
                        if (isCollapsed) {
                            newRow.collapsed = true;
                        }
                        acc.rows.push(newRow);
                        return acc;
                    }, {
                        promises: [],
                        rows: []
                    });
                    // Wait for all promises and update fields with the results
                    await Promise.all(promises);
                    if (rows) {
                        fieldState.rows = rows;
                    }
                    // Add values to field state
                    if (data[field.name] !== null) {
                        fieldState.value = forceFullValue ? arrayValue : arrayValue.length;
                        fieldState.initialValue = forceFullValue ? arrayValue : arrayValue.length;
                        if (arrayValue.length > 0) {
                            fieldState.disableFormData = true;
                        }
                    }
                    // Add field to state
                    if (!omitParents && (!filter || filter(args))) {
                        state[path] = fieldState;
                    }
                    break;
                }
            case 'blocks':
                {
                    const blocksValue = Array.isArray(data[field.name]) ? data[field.name] : [];
                    // Handle blocks filterOptions
                    let filterOptionsValidationResult = null;
                    if (field.filterOptions) {
                        filterOptionsValidationResult = await (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["validateBlocksFilterOptions"])({
                            id,
                            data: fullData,
                            filterOptions: field.filterOptions,
                            req,
                            siblingData: data,
                            value: data[field.name]
                        });
                        fieldState.blocksFilterOptions = filterOptionsValidationResult.allowedBlockSlugs;
                    }
                    const { promises, rowMetadata } = blocksValue.reduce((acc, row, i)=>{
                        const blockTypeToMatch = row.blockType;
                        const block = req.payload.blocks[blockTypeToMatch] ?? (field.blockReferences ?? field.blocks).find((blockType)=>typeof blockType !== 'string' && blockType.slug === blockTypeToMatch);
                        if (!block) {
                            throw new Error(`Block with type "${row.blockType}" was found in block data, but no block with that type is defined in the config for field with schema path ${schemaPath}.`);
                        }
                        const { blockSelect, blockSelectMode } = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getBlockSelect"])({
                            block,
                            select: select?.[field.name],
                            selectMode
                        });
                        const rowPath = path + '.' + i;
                        if (block) {
                            row.id = row?.id || new ObjectId().toHexString();
                            if (!omitParents && (!filter || filter(args))) {
                                // Handle block `id` field
                                const idKey = rowPath + '.id';
                                state[idKey] = {
                                    initialValue: row.id,
                                    value: row.id
                                };
                                // If the blocks field fails filterOptions validation, add error paths to the individual blocks that are no longer allowed
                                if (filterOptionsValidationResult?.invalidBlockSlugs?.length && filterOptionsValidationResult.invalidBlockSlugs.includes(row.blockType)) {
                                    state[idKey].errorMessage = req.t('validation:invalidBlock', {
                                        block: row.blockType
                                    });
                                    state[idKey].valid = false;
                                    addErrorPathToParent(idKey);
                                    // If the error is due to block filterOptions, we want the blocks field (fieldState) to include all the filterOptions-related
                                    // error paths for each sub-block, not for the validation result of the block itself. Otherwise, say there are 2 invalid blocks,
                                    // the blocks field will have 3 instead of 2 error paths - one for itself, and one for each invalid block.
                                    // Instead, we want only the 2 error paths for the individual, invalid blocks.
                                    fieldState.errorPaths = fieldState.errorPaths.filter((errorPath)=>errorPath !== path);
                                }
                                if (includeSchema) {
                                    state[idKey].fieldSchema = includeSchema ? block.fields.find((blockField)=>(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsID"])(blockField)) : undefined;
                                }
                                // Handle `blockType` field
                                const fieldKey = rowPath + '.blockType';
                                state[fieldKey] = {
                                    initialValue: row.blockType,
                                    value: row.blockType
                                };
                                if (addedByServer) {
                                    state[fieldKey].addedByServer = addedByServer;
                                }
                                if (includeSchema) {
                                    state[fieldKey].fieldSchema = block.fields.find((blockField)=>'name' in blockField && blockField.name === 'blockType');
                                }
                                // Handle `blockName` field
                                const blockNameKey = rowPath + '.blockName';
                                state[blockNameKey] = {};
                                if (row.blockName) {
                                    state[blockNameKey].initialValue = row.blockName;
                                    state[blockNameKey].value = row.blockName;
                                }
                                if (includeSchema) {
                                    state[blockNameKey].fieldSchema = block.fields.find((blockField)=>'name' in blockField && blockField.name === 'blockName');
                                }
                            }
                            acc.promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                                id,
                                addErrorPathToParent,
                                anyParentLocalized: field.localized || anyParentLocalized,
                                blockData: row,
                                clientFieldSchemaMap,
                                collectionSlug,
                                data: row,
                                fields: block.fields,
                                fieldSchemaMap,
                                filter,
                                forceFullValue,
                                fullData,
                                includeSchema,
                                mockRSCs,
                                omitParents,
                                operation,
                                parentIndexPath: '',
                                parentPassesCondition: passesCondition,
                                parentPath: rowPath,
                                parentSchemaPath: schemaPath + '.' + block.slug,
                                permissions: fieldPermissions === true ? fieldPermissions : parentPermissions?.[field.name]?.blocks?.[block.slug] === true ? true : parentPermissions?.[field.name]?.blocks?.[block.slug]?.fields || {},
                                preferences,
                                previousFormState,
                                readOnly,
                                renderAllFields,
                                renderFieldFn,
                                req,
                                select: typeof blockSelect === 'object' ? blockSelect : undefined,
                                selectMode: blockSelectMode,
                                skipConditionChecks,
                                skipValidation,
                                state
                            }));
                            // First, check if `previousFormState` has a matching row
                            const previousRow = (previousFormState?.[path]?.rows || []).find((prevRow)=>prevRow.id === row.id);
                            const newRow = {
                                id: row.id,
                                blockType: row.blockType,
                                isLoading: false
                            };
                            if (previousRow?.lastRenderedPath) {
                                newRow.lastRenderedPath = previousRow.lastRenderedPath;
                            }
                            acc.rowMetadata.push(newRow);
                            const isCollapsed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["isRowCollapsed"])({
                                collapsedPrefs: preferences?.fields?.[path]?.collapsed,
                                field,
                                previousRow,
                                row
                            });
                            if (isCollapsed) {
                                acc.rowMetadata[acc.rowMetadata.length - 1].collapsed = true;
                            }
                        }
                        return acc;
                    }, {
                        promises: [],
                        rowMetadata: []
                    });
                    await Promise.all(promises);
                    // Add values to field state
                    if (data[field.name] === null) {
                        fieldState.value = null;
                        fieldState.initialValue = null;
                    } else {
                        fieldState.value = forceFullValue ? blocksValue : blocksValue.length;
                        fieldState.initialValue = forceFullValue ? blocksValue : blocksValue.length;
                        if (blocksValue.length > 0) {
                            fieldState.disableFormData = true;
                        }
                    }
                    fieldState.rows = rowMetadata;
                    // Add field to state
                    if (!omitParents && (!filter || filter(args))) {
                        state[path] = fieldState;
                    }
                    break;
                }
            case 'group':
                {
                    if (!filter || filter(args)) {
                        fieldState.disableFormData = true;
                        state[path] = fieldState;
                    }
                    const groupSelect = select?.[field.name];
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                        id,
                        addErrorPathToParent,
                        anyParentLocalized: field.localized || anyParentLocalized,
                        blockData,
                        clientFieldSchemaMap,
                        collectionSlug,
                        data: data?.[field.name] || {},
                        fields: field.fields,
                        fieldSchemaMap,
                        filter,
                        forceFullValue,
                        fullData,
                        includeSchema,
                        mockRSCs,
                        omitParents,
                        operation,
                        parentIndexPath: '',
                        parentPassesCondition: passesCondition,
                        parentPath: path,
                        parentSchemaPath: schemaPath,
                        permissions: typeof fieldPermissions === 'boolean' ? fieldPermissions : fieldPermissions?.fields,
                        preferences,
                        previousFormState,
                        readOnly,
                        renderAllFields,
                        renderFieldFn,
                        req,
                        select: typeof groupSelect === 'object' ? groupSelect : undefined,
                        selectMode,
                        skipConditionChecks,
                        skipValidation,
                        state
                    });
                    break;
                }
            case 'relationship':
            case 'upload':
                {
                    if (field.filterOptions) {
                        if (typeof field.filterOptions === 'object') {
                            if (typeof field.relationTo === 'string') {
                                fieldState.filterOptions = {
                                    [field.relationTo]: field.filterOptions
                                };
                            } else {
                                fieldState.filterOptions = field.relationTo.reduce((acc, relation)=>{
                                    acc[relation] = field.filterOptions;
                                    return acc;
                                }, {});
                            }
                        }
                        if (typeof field.filterOptions === 'function') {
                            const query = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$resolveFilterOptions$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["resolveFilterOptions"])(field.filterOptions, {
                                id,
                                blockData,
                                data: fullData,
                                relationTo: field.relationTo,
                                req,
                                siblingData: data,
                                user: req.user
                            });
                            fieldState.filterOptions = query;
                        }
                    }
                    if (field.hasMany) {
                        const relationshipValue = Array.isArray(data[field.name]) ? data[field.name].map((relationship)=>{
                            if (Array.isArray(field.relationTo)) {
                                return {
                                    relationTo: relationship.relationTo,
                                    value: relationship.value && typeof relationship.value === 'object' ? relationship.value?.id : relationship.value
                                };
                            }
                            if (typeof relationship === 'object' && relationship !== null) {
                                return relationship.id;
                            }
                            return relationship;
                        }) : undefined;
                        fieldState.value = relationshipValue;
                        fieldState.initialValue = relationshipValue;
                    } else if (Array.isArray(field.relationTo)) {
                        if (data[field.name] && typeof data[field.name] === 'object' && 'relationTo' in data[field.name] && 'value' in data[field.name]) {
                            const value = typeof data[field.name]?.value === 'object' && data[field.name]?.value && 'id' in data[field.name].value ? data[field.name].value.id : data[field.name].value;
                            const relationshipValue = {
                                relationTo: data[field.name]?.relationTo,
                                value
                            };
                            fieldState.value = relationshipValue;
                            fieldState.initialValue = relationshipValue;
                        }
                    } else {
                        const relationshipValue = data[field.name] && typeof data[field.name] === 'object' && 'id' in data[field.name] ? data[field.name].id : data[field.name];
                        fieldState.value = relationshipValue;
                        fieldState.initialValue = relationshipValue;
                    }
                    if (!filter || filter(args)) {
                        state[path] = fieldState;
                    }
                    break;
                }
            case 'select':
                {
                    if (typeof field.filterOptions === 'function') {
                        fieldState.selectFilterOptions = field.filterOptions({
                            data: fullData,
                            options: field.options,
                            req,
                            siblingData: data
                        });
                    }
                    if (data[field.name] !== undefined) {
                        fieldState.value = data[field.name];
                        fieldState.initialValue = data[field.name];
                    }
                    if (!filter || filter(args)) {
                        state[path] = fieldState;
                    }
                    break;
                }
            default:
                {
                    if (data[field.name] !== undefined) {
                        fieldState.value = data[field.name];
                        fieldState.initialValue = data[field.name];
                    }
                    // Add field to state
                    if (!filter || filter(args)) {
                        state[path] = fieldState;
                    }
                    break;
                }
        }
    } else if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldHasSubFields"])(field) && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field)) {
        // Handle field types that do not use names (row, collapsible, unnamed group etc)
        if (!filter || filter(args)) {
            state[path] = {
                disableFormData: true
            };
            // Presentational containers are hidden client-side via `withCondition`, which reads
            // `passesCondition` from their own state entry. Must be set here since these fields
            // are excluded from the short-circuit above (which would otherwise carry the flag).
            if (passesCondition === false) {
                state[path].passesCondition = false;
            }
        }
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
            id,
            mockRSCs,
            select,
            selectMode,
            // passthrough parent functionality
            addErrorPathToParent: addErrorPathToParentArg,
            anyParentLocalized: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsLocalized"])(field) || anyParentLocalized,
            blockData,
            clientFieldSchemaMap,
            collectionSlug,
            data,
            fields: field.fields,
            fieldSchemaMap,
            filter,
            forceFullValue,
            fullData,
            includeSchema,
            omitParents,
            operation,
            parentIndexPath: indexPath,
            parentPassesCondition: passesCondition,
            parentPath: path,
            parentSchemaPath: schemaPath,
            permissions: parentPermissions,
            preferences,
            previousFormState,
            readOnly,
            renderAllFields,
            renderFieldFn,
            req,
            skipConditionChecks,
            skipValidation,
            state
        });
    } else if (field.type === 'tab') {
        const isNamedTab = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["tabHasName"])(field);
        if (isNamedTab) {
            const shouldContinue = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["stripUnselectedFields"])({
                field: {
                    ...field,
                    type: 'tab'
                },
                select,
                selectMode,
                siblingDoc: data?.[field.name] || {}
            });
            if (!shouldContinue) {
                return;
            }
        }
        // Tab visibility on the client is keyed by `field.id`, not `path` (like all other fields).
        if (field?.id) {
            state[field.id] = {
                passesCondition
            };
            // Flag newly added tab entries so the client accepts them during merge.
            // Otherwise, tabs revealed after a hidden ancestor becomes visible would never make it into client form state.
            if (!renderAllFields && !previousFormState?.[field.id]) {
                state[field.id].addedByServer = true;
            }
        }
        if (!passesCondition) {
            return;
        }
        let childPermissions;
        let tabSelect;
        if (isNamedTab) {
            if (parentPermissions === true) {
                childPermissions = true;
            } else {
                const tabPermissions = parentPermissions?.[field.name];
                childPermissions = tabPermissions === true ? true : tabPermissions?.fields;
            }
            if (typeof select?.[field.name] === 'object') {
                tabSelect = select?.[field.name];
            }
        } else {
            childPermissions = parentPermissions;
            tabSelect = select;
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
            id,
            addErrorPathToParent: addErrorPathToParentArg,
            anyParentLocalized: field.localized || anyParentLocalized,
            blockData,
            clientFieldSchemaMap,
            collectionSlug,
            data: isNamedTab ? data?.[field.name] || {} : data,
            fields: field.fields,
            fieldSchemaMap,
            filter,
            forceFullValue,
            fullData,
            includeSchema,
            mockRSCs,
            omitParents,
            operation,
            parentIndexPath: indexPath,
            parentPassesCondition: passesCondition,
            parentPath: path,
            parentSchemaPath: schemaPath,
            permissions: childPermissions,
            preferences,
            previousFormState,
            readOnly,
            renderAllFields,
            renderFieldFn,
            req,
            select: tabSelect,
            selectMode,
            skipConditionChecks,
            skipValidation,
            state
        });
    } else if (field.type === 'tabs') {
        if (!filter || filter(args)) {
            state[path] = {
                disableFormData: true
            };
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
            id,
            addErrorPathToParent: addErrorPathToParentArg,
            anyParentLocalized: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsLocalized"])(field) || anyParentLocalized,
            blockData,
            clientFieldSchemaMap,
            collectionSlug,
            data,
            fields: field.tabs.map((tab)=>({
                    ...tab,
                    type: 'tab'
                })),
            fieldSchemaMap,
            filter,
            forceFullValue,
            fullData,
            includeSchema,
            omitParents,
            operation,
            parentIndexPath: indexPath,
            parentPassesCondition: passesCondition,
            parentPath: path,
            parentSchemaPath: schemaPath,
            permissions: parentPermissions,
            preferences,
            previousFormState,
            renderAllFields,
            renderFieldFn,
            req,
            select,
            selectMode,
            skipConditionChecks,
            skipValidation,
            state
        });
    } else if (field.type === 'ui') {
        if (!filter || filter(args)) {
            state[path] = fieldState;
            state[path].disableFormData = true;
        }
    }
    if (renderFieldFn && !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldIsHiddenOrDisabled"])(field)) {
        const fieldConfig = fieldSchemaMap.get(schemaPath);
        if (!fieldConfig && !mockRSCs) {
            if (schemaPath.endsWith('.blockType')) {
                return;
            } else {
                throw new Error(`Field config not found for ${schemaPath}`);
            }
        }
        if (!state[path]) {
            // Some fields (ie `Tab`) do not live in form state
            // therefore we cannot attach customComponents to them
            return;
        }
        if (addedByServer) {
            state[path].addedByServer = addedByServer;
        }
        renderFieldFn({
            id,
            clientFieldSchemaMap,
            collectionSlug,
            data: fullData,
            fieldConfig: fieldConfig,
            fieldSchemaMap,
            fieldState: state[path],
            formState: state,
            indexPath,
            lastRenderedPath,
            mockRSCs,
            operation,
            parentPath,
            parentSchemaPath,
            path,
            permissions: fieldPermissions,
            preferences,
            previousFieldState: previousFormState?.[path],
            readOnly,
            renderAllFields,
            req,
            schemaPath,
            siblingData: data
        });
    }
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/index.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "calculateDefaultValues",
    ()=>calculateDefaultValues
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
const calculateDefaultValues = async ({ id, data, fields, locale, req, select, selectMode, user })=>{
    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
        id,
        data,
        fields,
        locale,
        req,
        select,
        selectMode,
        siblingData: data,
        user
    });
    return data;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "iterateFields",
    ()=>iterateFields
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/promise.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
const iterateFields = async ({ id, data, fields, locale, req, select, selectMode, siblingData, user })=>{
    const promises = [];
    fields.forEach((field)=>{
        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["defaultValuePromise"])({
            id,
            data,
            field,
            locale,
            req,
            select,
            selectMode,
            siblingData,
            user
        }));
    });
    await Promise.all(promises);
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/promise.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "defaultValuePromise",
    ()=>defaultValuePromise
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
const defaultValuePromise = async ({ id, data, field, locale, req, select, selectMode, siblingData, user })=>{
    const shouldContinue = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["stripUnselectedFields"])({
        field,
        select,
        selectMode,
        siblingDoc: siblingData
    });
    if (!shouldContinue) {
        return;
    }
    if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field)) {
        if (typeof siblingData[field.name] === 'undefined' && typeof field.defaultValue !== 'undefined') {
            try {
                siblingData[field.name] = await (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getDefaultValue"])({
                    defaultValue: field.defaultValue,
                    locale,
                    req,
                    user,
                    value: siblingData[field.name]
                });
            } catch (err) {
                req.payload.logger.error({
                    err,
                    msg: `Error calculating default value for field: ${field.name}`
                });
            }
        }
    }
    // Traverse subfields
    switch(field.type){
        case 'array':
            {
                const rows = siblingData[field.name];
                if (Array.isArray(rows)) {
                    const promises = [];
                    const arraySelect = select?.[field.name];
                    rows.forEach((row)=>{
                        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                            id,
                            data,
                            fields: field.fields,
                            locale,
                            req,
                            select: typeof arraySelect === 'object' ? arraySelect : undefined,
                            selectMode,
                            siblingData: row,
                            user
                        }));
                    });
                    await Promise.all(promises);
                }
                break;
            }
        case 'blocks':
            {
                const rows = siblingData[field.name];
                if (Array.isArray(rows)) {
                    const promises = [];
                    rows.forEach((row)=>{
                        const blockTypeToMatch = row.blockType;
                        const block = req.payload.blocks[blockTypeToMatch] ?? (field.blockReferences ?? field.blocks).find((blockType)=>typeof blockType !== 'string' && blockType.slug === blockTypeToMatch);
                        const { blockSelect, blockSelectMode } = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getBlockSelect"])({
                            block,
                            select: select?.[field.name],
                            selectMode
                        });
                        if (block) {
                            row.blockType = blockTypeToMatch;
                            promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                                id,
                                data,
                                fields: block.fields,
                                locale,
                                req,
                                select: typeof blockSelect === 'object' ? blockSelect : undefined,
                                selectMode: blockSelectMode,
                                siblingData: row,
                                user
                            }));
                        }
                    });
                    await Promise.all(promises);
                }
                break;
            }
        case 'collapsible':
        case 'row':
            {
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                    id,
                    data,
                    fields: field.fields,
                    locale,
                    req,
                    select,
                    selectMode,
                    siblingData,
                    user
                });
                break;
            }
        case 'group':
            {
                if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field)) {
                    if (typeof siblingData[field.name] !== 'object') {
                        siblingData[field.name] = {};
                    }
                    const groupData = siblingData[field.name];
                    const groupSelect = select?.[field.name];
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                        id,
                        data,
                        fields: field.fields,
                        locale,
                        req,
                        select: typeof groupSelect === 'object' ? groupSelect : undefined,
                        selectMode,
                        siblingData: groupData,
                        user
                    });
                } else {
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                        id,
                        data,
                        fields: field.fields,
                        locale,
                        req,
                        select,
                        selectMode,
                        siblingData,
                        user
                    });
                }
                break;
            }
        case 'tab':
            {
                let tabSiblingData;
                const isNamedTab = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["tabHasName"])(field);
                let tabSelect;
                if (isNamedTab) {
                    if (typeof siblingData[field.name] !== 'object') {
                        siblingData[field.name] = {};
                    }
                    tabSiblingData = siblingData[field.name];
                    if (typeof select?.[field.name] === 'object') {
                        tabSelect = select?.[field.name];
                    }
                } else {
                    tabSiblingData = siblingData;
                    tabSelect = select;
                }
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                    id,
                    data,
                    fields: field.fields,
                    locale,
                    req,
                    select: tabSelect,
                    selectMode,
                    siblingData: tabSiblingData,
                    user
                });
                break;
            }
        case 'tabs':
            {
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
                    id,
                    data,
                    fields: field.tabs.map((tab)=>({
                            ...tab,
                            type: 'tab'
                        })),
                    locale,
                    req,
                    select,
                    selectMode,
                    siblingData,
                    user
                });
                break;
            }
        default:
            {
                break;
            }
    }
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/index.js [app-route] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "fieldSchemasToFormState",
    ()=>fieldSchemasToFormState
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/index.js [app-route] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
const fieldSchemasToFormState = async ({ id, clientFieldSchemaMap, collectionSlug, data = {}, documentData, fields, fieldSchemaMap, initialBlockData, mockRSCs, operation, permissions, preferences, previousFormState, readOnly, renderAllFields, renderFieldFn, req, schemaPath, select, selectMode, skipValidation })=>{
    if (!clientFieldSchemaMap && renderFieldFn) {
        // eslint-disable-next-line no-console
        console.warn('clientFieldSchemaMap is not passed to fieldSchemasToFormState - this will reduce performance');
    }
    if (fields && fields.length) {
        const state = {};
        const dataWithDefaultValues = {
            ...data
        };
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["calculateDefaultValues"])({
            id,
            data: dataWithDefaultValues,
            fields,
            locale: req.locale,
            req,
            select,
            selectMode,
            siblingData: dataWithDefaultValues,
            user: req.user
        });
        let fullData = dataWithDefaultValues;
        if (documentData) {
            // By the time this function is used to get form state for nested forms, their default values should have already been calculated
            // => no need to run calculateDefaultValues here
            fullData = documentData;
        }
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["iterateFields"])({
            id,
            addErrorPathToParent: null,
            blockData: initialBlockData,
            clientFieldSchemaMap,
            collectionSlug,
            data: dataWithDefaultValues,
            fields,
            fieldSchemaMap,
            fullData,
            mockRSCs,
            operation,
            parentIndexPath: '',
            parentPassesCondition: true,
            parentPath: '',
            parentSchemaPath: schemaPath,
            permissions,
            preferences,
            previousFormState,
            readOnly,
            renderAllFields,
            renderFieldFn,
            req,
            select,
            selectMode,
            skipValidation,
            state
        });
        return state;
    }
    return {};
};
;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/isRowCollapsed.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isRowCollapsed",
    ()=>isRowCollapsed
]);
function isRowCollapsed({ collapsedPrefs, field, previousRow, row }) {
    if (previousRow && 'collapsed' in previousRow) {
        return previousRow.collapsed ?? false;
    }
    // If previousFormState is `undefined`, check preferences
    if (collapsedPrefs !== undefined) {
        return collapsedPrefs.includes(row.id) // Check if collapsed in preferences
        ;
    }
    // If neither exists, fallback to `field.admin.initCollapsed`
    return field.admin.initCollapsed;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "iterateFields",
    ()=>iterateFields
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/addFieldStatePromise.js [app-route] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
const iterateFields = async ({ id, addErrorPathToParent: addErrorPathToParentArg, anyParentLocalized = false, blockData, clientFieldSchemaMap, collectionSlug, data, fields, fieldSchemaMap, filter, forceFullValue = false, fullData, includeSchema = false, mockRSCs, omitParents = false, operation, parentIndexPath, parentPassesCondition = true, parentPath, parentSchemaPath, permissions, preferences, previousFormState, readOnly, renderAllFields, renderFieldFn: renderFieldFn, req, select, selectMode, skipConditionChecks = false, skipValidation = false, state = {} })=>{
    const promises = [];
    fields.forEach((field, fieldIndex)=>{
        let passesCondition = true;
        const { indexPath, path, schemaPath } = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getFieldPaths"])({
            field,
            index: fieldIndex,
            parentIndexPath,
            parentPath,
            parentSchemaPath
        });
        if (path !== 'id') {
            const shouldContinue = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["stripUnselectedFields"])({
                field,
                select,
                selectMode,
                siblingDoc: data
            });
            if (!shouldContinue) {
                return;
            }
        }
        const pathSegments = path ? path.split('.') : [];
        if (!skipConditionChecks) {
            try {
                passesCondition = Boolean((field?.admin?.condition ? Boolean(field.admin.condition(fullData || {}, data || {}, {
                    blockData,
                    operation,
                    path: pathSegments,
                    user: req.user
                })) : true) && parentPassesCondition);
            } catch (err) {
                passesCondition = false;
                req.payload.logger.error({
                    err,
                    msg: `Error evaluating field condition at path: ${path}`
                });
            }
        }
        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$route$5d$__$28$ecmascript$29$__["addFieldStatePromise"])({
            id,
            addErrorPathToParent: addErrorPathToParentArg,
            anyParentLocalized,
            blockData,
            clientFieldSchemaMap,
            collectionSlug,
            data,
            field,
            fieldIndex,
            fieldSchemaMap,
            filter,
            forceFullValue,
            fullData,
            includeSchema,
            indexPath,
            mockRSCs,
            omitParents,
            operation,
            parentIndexPath,
            parentPath,
            parentPermissions: permissions,
            parentSchemaPath,
            passesCondition,
            path,
            preferences,
            previousFormState,
            readOnly,
            renderAllFields,
            renderFieldFn,
            req,
            schemaPath,
            select,
            selectMode,
            skipConditionChecks,
            skipValidation,
            state
        }));
    });
    await Promise.all(promises);
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/buildFieldSchemaMap/traverseFields.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "traverseFields",
    ()=>traverseFields
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
const traverseFields = ({ config, fields, i18n, parentIndexPath, parentSchemaPath, schemaMap })=>{
    for (const [index, field] of fields.entries()){
        const { indexPath, schemaPath } = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["getFieldPaths"])({
            field,
            index,
            parentIndexPath,
            parentSchemaPath
        });
        schemaMap.set(schemaPath, field);
        switch(field.type){
            case 'array':
                traverseFields({
                    config,
                    fields: field.fields,
                    i18n,
                    parentIndexPath: '',
                    parentSchemaPath: schemaPath,
                    schemaMap
                });
                break;
            case 'blocks':
                ;
                (field.blockReferences ?? field.blocks).map((_block)=>{
                    // TODO: iterate over blocks mapped to block slug in v4, or pass through payload.blocks
                    const block = typeof _block === 'string' ? config.blocks.find((b)=>b.slug === _block) : _block;
                    const blockSchemaPath = `${schemaPath}.${block.slug}`;
                    schemaMap.set(blockSchemaPath, block);
                    traverseFields({
                        config,
                        fields: block.fields,
                        i18n,
                        parentIndexPath: '',
                        parentSchemaPath: schemaPath + '.' + block.slug,
                        schemaMap
                    });
                });
                break;
            case 'collapsible':
            case 'row':
                traverseFields({
                    config,
                    fields: field.fields,
                    i18n,
                    parentIndexPath: indexPath,
                    parentSchemaPath: schemaPath,
                    schemaMap
                });
                break;
            case 'group':
                if ((0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["fieldAffectsData"])(field)) {
                    traverseFields({
                        config,
                        fields: field.fields,
                        i18n,
                        parentIndexPath: '',
                        parentSchemaPath: schemaPath,
                        schemaMap
                    });
                } else {
                    traverseFields({
                        config,
                        fields: field.fields,
                        i18n,
                        parentIndexPath: indexPath,
                        parentSchemaPath: schemaPath,
                        schemaMap
                    });
                }
                break;
            case 'richText':
                {
                    if (!field?.editor) {
                        throw new __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["MissingEditorProp"](field) // while we allow disabling editor functionality, you should not have any richText fields defined if you do not have an editor
                        ;
                    }
                    if (typeof field.editor === 'function') {
                        throw new Error('Attempted to access unsanitized rich text editor.');
                    }
                    if (typeof field.editor.generateSchemaMap === 'function') {
                        field.editor.generateSchemaMap({
                            config,
                            field,
                            i18n,
                            schemaMap,
                            schemaPath
                        });
                    }
                    break;
                }
            case 'tab':
                {
                    const isNamedTab = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["tabHasName"])(field);
                    traverseFields({
                        config,
                        fields: field.fields,
                        i18n,
                        parentIndexPath: isNamedTab ? '' : indexPath,
                        parentSchemaPath: schemaPath,
                        schemaMap
                    });
                    break;
                }
            case 'tabs':
                {
                    traverseFields({
                        config,
                        fields: field.tabs.map((tab)=>({
                                ...tab,
                                type: 'tab'
                            })),
                        i18n,
                        parentIndexPath: indexPath,
                        parentSchemaPath: schemaPath,
                        schemaMap
                    });
                    break;
                }
        }
    }
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/removeUndefined.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "removeUndefined",
    ()=>removeUndefined
]);
function removeUndefined(obj) {
    return Object.fromEntries(Object.entries(obj).filter(([, value])=>value !== undefined));
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/resolveFilterOptions.js [app-route] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "resolveFilterOptions",
    ()=>resolveFilterOptions
]);
const resolveFilterOptions = async (filterOptions, options)=>{
    const { relationTo } = options;
    const relations = Array.isArray(relationTo) ? relationTo : [
        relationTo
    ];
    const query = {};
    if (typeof filterOptions !== 'undefined') {
        await Promise.all(relations.map(async (relation)=>{
            query[relation] = typeof filterOptions === 'function' ? await filterOptions({
                ...options,
                relationTo: relation
            }) : filterOptions;
            if (query[relation] === true) {
                query[relation] = {};
            }
            // this is an ugly way to prevent results from being returned
            if (query[relation] === false) {
                query[relation] = {
                    id: {
                        exists: false
                    }
                };
            }
        }));
    }
    return query;
};
}),
];

//# sourceMappingURL=0nrf_%40payloadcms_ui_dist_1bn4xny._.js.map