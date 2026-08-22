module.exports = [
"[externals]/crypto [external] (crypto, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("crypto", () => require("crypto"));

module.exports = mod;
}),
"[externals]/node:crypto [external] (node:crypto, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("node:crypto", () => require("node:crypto"));

module.exports = mod;
}),
"[externals]/url [external] (url, cjs)", ((__turbopack_context__, module, exports) => {

var mod = __turbopack_context__.x("url", () => require("url"));

module.exports = mod;
}),
"[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "fieldSuperAdminOnly",
    ()=>fieldSuperAdminOnly,
    "hasRole",
    ()=>hasRole,
    "isSuperAdmin",
    ()=>isSuperAdmin,
    "roleFieldAccess",
    ()=>roleFieldAccess,
    "superAdminOnly",
    ()=>superAdminOnly,
    "tenantIdsOf",
    ()=>tenantIdsOf,
    "tenantScopedAccess",
    ()=>tenantScopedAccess,
    "tenantSelfAccess",
    ()=>tenantSelfAccess
]);
const isSuperAdmin = (user)=>Boolean(user && user.role === 'super_admin');
const tenantIdsOf = (user)=>{
    const rows = user?.tenants ?? [];
    return rows.map((row)=>typeof row.tenant === 'object' && row.tenant !== null ? row.tenant.id : row.tenant).filter((value)=>value !== undefined && value !== null);
};
const hasRole = (...roles)=>({ req })=>{
        const user = req.user;
        if (!user) return false;
        if (user.role === 'super_admin') return true;
        return Boolean(user.role && roles.includes(user.role));
    };
const tenantScopedAccess = (options = {})=>({ req })=>{
        const user = req.user;
        if (!user) return false;
        if (isSuperAdmin(user)) return true;
        if (options.roles && user.role && !options.roles.includes(user.role)) return false;
        const tenants = tenantIdsOf(user);
        if (tenants.length === 0) return false;
        return {
            tenant: {
                in: tenants
            }
        };
    };
const tenantSelfAccess = ({ req })=>{
    const user = req.user;
    if (!user) return false;
    if (isSuperAdmin(user)) return true;
    const tenants = tenantIdsOf(user);
    if (tenants.length === 0) return false;
    return {
        id: {
            in: tenants
        }
    };
};
const superAdminOnly = ({ req })=>isSuperAdmin(req.user);
const fieldSuperAdminOnly = ({ req })=>isSuperAdmin(req.user);
const roleFieldAccess = ({ req })=>isSuperAdmin(req.user);
}),
"[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/importMap.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "importMap",
    ()=>importMap
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$WatchTenantCollection$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/WatchTenantCollection/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$TenantField$2f$index$2e$client$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/TenantField/index.client.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Overview$2f$OverviewComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Overview/OverviewComponent.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaTitle$2f$MetaTitleComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaTitle/MetaTitleComponent.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaDescription$2f$MetaDescriptionComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaDescription/MetaDescriptionComponent.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaImage$2f$MetaImageComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaImage/MetaImageComponent.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Preview$2f$PreviewComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Preview/PreviewComponent.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$AssignTenantFieldModal$2f$index$2e$client$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/AssignTenantFieldModal/index.client.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$GlobalViewRedirect$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/GlobalViewRedirect/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$TenantSelector$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/TenantSelector/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$widgets$2f$CollectionCards$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/widgets/CollectionCards/index.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$GlobalViewRedirect$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$widgets$2f$CollectionCards$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$GlobalViewRedirect$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$widgets$2f$CollectionCards$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
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
;
const importMap = {
    "@payloadcms/plugin-multi-tenant/client#WatchTenantCollection": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$WatchTenantCollection$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["WatchTenantCollection"],
    "@payloadcms/plugin-multi-tenant/client#TenantField": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$TenantField$2f$index$2e$client$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TenantField"],
    "@payloadcms/plugin-seo/client#OverviewComponent": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Overview$2f$OverviewComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["OverviewComponent"],
    "@payloadcms/plugin-seo/client#MetaTitleComponent": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaTitle$2f$MetaTitleComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaTitleComponent"],
    "@payloadcms/plugin-seo/client#MetaDescriptionComponent": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaDescription$2f$MetaDescriptionComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaDescriptionComponent"],
    "@payloadcms/plugin-seo/client#MetaImageComponent": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaImage$2f$MetaImageComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaImageComponent"],
    "@payloadcms/plugin-seo/client#PreviewComponent": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Preview$2f$PreviewComponent$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PreviewComponent"],
    "@payloadcms/plugin-multi-tenant/client#AssignTenantFieldTrigger": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$AssignTenantFieldModal$2f$index$2e$client$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["AssignTenantFieldTrigger"],
    "@payloadcms/plugin-multi-tenant/rsc#GlobalViewRedirect": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$GlobalViewRedirect$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["GlobalViewRedirect"],
    "@payloadcms/plugin-multi-tenant/rsc#TenantSelector": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$TenantSelector$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TenantSelector"],
    "@payloadcms/plugin-multi-tenant/rsc#TenantSelectionProvider": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TenantSelectionProvider"],
    "@payloadcms/next/rsc#CollectionCards": __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$widgets$2f$CollectionCards$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CollectionCards"]
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/app/(payload)/layout.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
/* __next_internal_action_entry_do_not_use__ [{"403c62f39c09ad482f0a08a5dadad9fad114a16098":{"name":"$$RSC_SERVER_ACTION_0"}},"blueprints/payload-next-multisite/app/src/app/(payload)/layout.tsx",""] */ __turbopack_context__.s([
    "$$RSC_SERVER_ACTION_0",
    ()=>$$RSC_SERVER_ACTION_0,
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$webpack$2f$loaders$2f$next$2d$flight$2d$loader$2f$server$2d$reference$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/webpack/loaders/next-flight-loader/server-reference.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/payload.config.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/importMap.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$layouts$2f$Root$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/layouts/Root/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$handleServerFunctions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/handleServerFunctions.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$layouts$2f$Root$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$handleServerFunctions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$layouts$2f$Root$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$handleServerFunctions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
const $$RSC_SERVER_ACTION_0 = async function serverFunction(args) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$handleServerFunctions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["handleServerFunctions"])({
        ...args,
        config: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"],
        importMap: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["importMap"]
    });
};
(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$webpack$2f$loaders$2f$next$2d$flight$2d$loader$2f$server$2d$reference$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerServerReference"])($$RSC_SERVER_ACTION_0, "403c62f39c09ad482f0a08a5dadad9fad114a16098", null);
const serverFunction = $$RSC_SERVER_ACTION_0;
const Layout = ({ children })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$layouts$2f$Root$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["RootLayout"], {
        config: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"],
        importMap: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["importMap"],
        serverFunction: serverFunction,
        children: children
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/app/(payload)/layout.tsx",
        lineNumber: 18,
        columnNumber: 3
    }, ("TURBOPACK compile-time value", void 0));
const __TURBOPACK__default__export__ = Layout;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/app/(payload)/layout.tsx [app-rsc] (ecmascript, Next.js Server Component)", (function(__turbopack_context__){

__turbopack_context__.n(__turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(payload)/layout.tsx [app-rsc] (ecmascript)"));
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/Tenants.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Tenants",
    ()=>Tenants
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
const Tenants = {
    slug: 'tenants',
    labels: {
        singular: 'Сайт',
        plural: 'Сайты'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Управление сайтами',
        description: 'Каждый сайт — самостоятельный бренд, домен и SEO-политика.'
    },
    access: {
        create: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"],
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"],
        update: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"],
        read: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantSelfAccess"]
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название сайта'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            unique: true,
            index: true,
            label: 'Код сайта',
            admin: {
                description: 'Внутренний код: site_a, site_b, site_c. Не отображается посетителям.'
            },
            validate: (value)=>typeof value === 'string' && /^[a-z][a-z0-9_]{1,30}$/.test(value) ? true : 'Только строчные латинские буквы, цифры и подчёркивание'
        },
        {
            name: 'domain',
            type: 'text',
            required: true,
            unique: true,
            index: true,
            label: 'Домен',
            admin: {
                description: 'Домен без схемы. По нему запрос сопоставляется с сайтом.'
            }
        },
        {
            name: 'seoProfile',
            type: 'select',
            required: true,
            label: 'SEO-профиль',
            options: [
                {
                    label: 'CATALOG_AUTHORITY — полнота каталога',
                    value: 'catalog_authority'
                },
                {
                    label: 'RELEASE_PULSE — новые серии и расписание',
                    value: 'release_pulse'
                },
                {
                    label: 'EDITORIAL_GUIDE — редакционные материалы',
                    value: 'editorial_guide'
                }
            ]
        },
        {
            name: 'theme',
            type: 'select',
            required: true,
            label: 'Тема оформления',
            options: [
                {
                    label: 'Портальная светлая',
                    value: 'portal_light'
                },
                {
                    label: 'Динамичная лента',
                    value: 'pulse'
                },
                {
                    label: 'Редакционная спокойная',
                    value: 'editorial'
                }
            ]
        },
        {
            name: 'indexingEnabled',
            type: 'checkbox',
            defaultValue: false,
            label: 'Разрешить индексацию поисковыми системами',
            admin: {
                description: 'Пока выключено, сайт отдаёт noindex целиком. Включается только после проверки контента и SEO.'
            }
        },
        {
            name: 'allowGuestComments',
            type: 'checkbox',
            defaultValue: false,
            label: 'Разрешить комментарии без регистрации'
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/Users.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Users",
    ()=>Users
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
const Users = {
    slug: 'users',
    labels: {
        singular: 'Пользователь',
        plural: 'Пользователи'
    },
    auth: {
        tokenExpiration: 60 * 60 * 8,
        maxLoginAttempts: 10,
        lockTime: 10 * 60 * 1000
    },
    admin: {
        useAsTitle: 'email',
        group: 'Управление сайтами'
    },
    access: {
        create: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"],
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"],
        read: ({ req })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isSuperAdmin"])(req.user) ? true : {
                id: {
                    equals: req.user?.id
                }
            },
        update: ({ req })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isSuperAdmin"])(req.user) ? true : {
                id: {
                    equals: req.user?.id
                }
            }
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            label: 'Имя'
        },
        {
            name: 'role',
            type: 'select',
            required: true,
            defaultValue: 'editor',
            label: 'Роль',
            // Роль назначает только супер-администратор: иначе редактор повысит себя сам.
            access: {
                create: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["roleFieldAccess"],
                update: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["roleFieldAccess"]
            },
            options: [
                {
                    label: 'Супер-администратор',
                    value: 'super_admin'
                },
                {
                    label: 'Администратор сайта',
                    value: 'site_admin'
                },
                {
                    label: 'Редактор',
                    value: 'editor'
                },
                {
                    label: 'Модератор',
                    value: 'moderator'
                },
                {
                    label: 'Аналитик (только чтение)',
                    value: 'analyst'
                }
            ]
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/catalog.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CatalogMedia",
    ()=>CatalogMedia,
    "Episodes",
    ()=>Episodes,
    "Genres",
    ()=>Genres,
    "RightsRecords",
    ()=>RightsRecords,
    "Seasons",
    ()=>Seasons,
    "SourceRecords",
    ()=>SourceRecords,
    "Studios",
    ()=>Studios,
    "Titles",
    ()=>Titles,
    "Voices",
    ()=>Voices
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
/**
 * Общий фактический каталог. Эти данные одинаковы для всех сайтов: один и тот же
 * тайтл не должен существовать в трёх несогласованных копиях. Редакционные тексты,
 * URL и SEO живут отдельно, в TenantTitles.
 */ const provenanceFields = [
    {
        type: 'collapsible',
        label: 'Происхождение данных',
        admin: {
            initCollapsed: true
        },
        fields: [
            {
                name: 'source',
                type: 'select',
                label: 'Источник',
                defaultValue: 'manual',
                options: [
                    {
                        label: 'Ручной ввод редактора',
                        value: 'manual'
                    },
                    {
                        label: 'Content API провайдера',
                        value: 'provider_api'
                    },
                    {
                        label: 'Импорт из переданного файла',
                        value: 'import_file'
                    }
                ]
            },
            {
                name: 'sourceRef',
                type: 'text',
                label: 'Ссылка на запись источника'
            },
            {
                name: 'sourceUpdatedAt',
                type: 'date',
                label: 'Дата данных в источнике'
            }
        ]
    }
];
const CatalogMedia = {
    slug: 'catalog-media',
    labels: {
        singular: 'Изображение каталога',
        plural: 'Изображения каталога'
    },
    admin: {
        group: 'Каталог (общий)',
        description: 'Постеры и кадры, общие для всех сайтов. Хранятся отдельно от медиатеки сайта: ' + 'общий тайтл не может ссылаться на файл одного сайта, иначе он утёк бы на остальные.'
    },
    upload: {
        staticDir: process.env.CATALOG_MEDIA_DIR ?? 'var/catalog-media',
        mimeTypes: [
            'image/png',
            'image/jpeg',
            'image/webp',
            'image/avif'
        ],
        imageSizes: [
            {
                name: 'card',
                width: 400,
                height: 600,
                position: 'centre'
            },
            {
                name: 'wide',
                width: 1200,
                height: 675,
                position: 'centre'
            }
        ]
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'alt',
            type: 'text',
            required: true,
            label: 'Альтернативный текст',
            admin: {
                description: 'Обязателен: без alt изображение не публикуется.'
            }
        },
        {
            name: 'rightsRecord',
            type: 'relationship',
            relationTo: 'rights-records',
            required: true,
            label: 'Запись о правах',
            admin: {
                description: 'Без подтверждённых прав изображение не попадает в публикацию.'
            }
        },
        ...provenanceFields
    ]
};
const Genres = {
    slug: 'genres',
    labels: {
        singular: 'Жанр',
        plural: 'Жанры'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Каталог (общий)'
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            unique: true,
            index: true,
            label: 'URL-код'
        }
    ]
};
const Studios = {
    slug: 'studios',
    labels: {
        singular: 'Студия',
        plural: 'Студии'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Каталог (общий)'
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            unique: true,
            index: true,
            label: 'URL-код'
        },
        ...provenanceFields
    ]
};
const Titles = {
    slug: 'titles',
    labels: {
        singular: 'Тайтл (общие факты)',
        plural: 'Тайтлы (общие факты)'
    },
    admin: {
        useAsTitle: 'primaryName',
        group: 'Каталог (общий)',
        description: 'Проверенные факты о тайтле. Тексты и SEO конкретного сайта — в разделе «Публикации сайта».',
        defaultColumns: [
            'primaryName',
            'kind',
            'status',
            'year'
        ]
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'primaryName',
            type: 'text',
            required: true,
            index: true,
            label: 'Основное название'
        },
        {
            name: 'englishName',
            type: 'text',
            label: 'Английское название'
        },
        {
            name: 'originalName',
            type: 'text',
            label: 'Оригинальное название'
        },
        {
            name: 'alternativeNames',
            type: 'array',
            label: 'Альтернативные названия',
            fields: [
                {
                    name: 'value',
                    type: 'text',
                    required: true,
                    label: 'Название'
                }
            ]
        },
        {
            name: 'kind',
            type: 'select',
            required: true,
            defaultValue: 'series',
            label: 'Тип',
            options: [
                {
                    label: 'Сериал',
                    value: 'series'
                },
                {
                    label: 'Фильм',
                    value: 'movie'
                },
                {
                    label: 'OVA/ONA',
                    value: 'ova'
                }
            ]
        },
        {
            name: 'status',
            type: 'select',
            required: true,
            defaultValue: 'ongoing',
            label: 'Статус выхода',
            options: [
                {
                    label: 'Выходит',
                    value: 'ongoing'
                },
                {
                    label: 'Завершён',
                    value: 'completed'
                },
                {
                    label: 'Анонс',
                    value: 'announced'
                }
            ]
        },
        {
            name: 'year',
            type: 'number',
            label: 'Год выхода',
            min: 1900,
            max: 2100
        },
        {
            name: 'factualSynopsis',
            type: 'textarea',
            label: 'Фактическое описание из источника',
            admin: {
                description: 'Факты из источника. Редакционный текст сайта пишется отдельно и не выдаётся за оригинальный.'
            }
        },
        {
            name: 'genres',
            type: 'relationship',
            relationTo: 'genres',
            hasMany: true,
            label: 'Жанры'
        },
        {
            name: 'studios',
            type: 'relationship',
            relationTo: 'studios',
            hasMany: true,
            label: 'Студии'
        },
        {
            name: 'poster',
            type: 'upload',
            relationTo: 'catalog-media',
            label: 'Постер'
        },
        {
            type: 'collapsible',
            label: 'Идентификаторы провайдера воспроизведения',
            admin: {
                initCollapsed: true,
                description: 'Заполняется только из разрешённого Content API или подтверждённой записи источника.'
            },
            fields: [
                {
                    name: 'playbackAggregator',
                    type: 'select',
                    label: 'Агрегатор',
                    options: [
                        {
                            label: 'kp',
                            value: 'kp'
                        },
                        {
                            label: 'mali',
                            value: 'mali'
                        },
                        {
                            label: 'mdl',
                            value: 'mdl'
                        }
                    ]
                },
                {
                    name: 'playbackTitleId',
                    type: 'text',
                    label: 'ID тайтла у агрегатора'
                },
                {
                    name: 'rightsRecord',
                    type: 'relationship',
                    relationTo: 'rights-records',
                    label: 'Запись о правах'
                }
            ]
        },
        {
            name: 'relatedTitles',
            type: 'relationship',
            relationTo: 'titles',
            hasMany: true,
            label: 'Связанные тайтлы',
            admin: {
                description: 'Только реальные связи. «Похожее» не придумывается.'
            }
        },
        ...provenanceFields
    ]
};
const Seasons = {
    slug: 'seasons',
    labels: {
        singular: 'Сезон',
        plural: 'Сезоны'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Каталог (общий)',
        defaultColumns: [
            'label',
            'title',
            'number'
        ]
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'title',
            type: 'relationship',
            relationTo: 'titles',
            required: true,
            index: true,
            label: 'Тайтл'
        },
        {
            name: 'number',
            type: 'number',
            required: true,
            min: 1,
            label: 'Номер сезона'
        },
        {
            name: 'label',
            type: 'text',
            label: 'Название сезона'
        },
        ...provenanceFields
    ]
};
const Episodes = {
    slug: 'episodes',
    labels: {
        singular: 'Серия',
        plural: 'Серии'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Каталог (общий)',
        defaultColumns: [
            'label',
            'season',
            'number',
            'airedAt'
        ]
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'season',
            type: 'relationship',
            relationTo: 'seasons',
            required: true,
            index: true,
            label: 'Сезон'
        },
        {
            name: 'number',
            type: 'number',
            required: true,
            min: 1,
            label: 'Номер серии'
        },
        {
            name: 'label',
            type: 'text',
            label: 'Название серии'
        },
        {
            name: 'airedAt',
            type: 'date',
            label: 'Дата выхода',
            admin: {
                description: 'Только известная дата. Пустое поле лучше выдуманного.'
            }
        },
        {
            name: 'playbackAvailable',
            type: 'checkbox',
            defaultValue: false,
            label: 'Воспроизведение доступно',
            admin: {
                description: 'Снимается автоматически, если провайдер сообщил об отсутствии данных.'
            }
        },
        ...provenanceFields
    ]
};
const RightsRecords = {
    slug: 'rights-records',
    labels: {
        singular: 'Запись о правах',
        plural: 'Права на контент'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Права и источники'
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'label',
            type: 'text',
            required: true,
            label: 'Обозначение'
        },
        {
            name: 'holder',
            type: 'text',
            required: true,
            label: 'Правообладатель'
        },
        {
            name: 'contractRef',
            type: 'text',
            required: true,
            label: 'Ссылка на договор/contract'
        },
        {
            name: 'territory',
            type: 'text',
            label: 'Территория'
        },
        {
            name: 'validUntil',
            type: 'date',
            label: 'Действует до'
        },
        {
            name: 'allowsPublication',
            type: 'checkbox',
            defaultValue: false,
            label: 'Разрешает публикацию',
            admin: {
                description: 'Без этого флага тайтл не публикуется ни на одном сайте.'
            }
        }
    ]
};
const SourceRecords = {
    slug: 'source-records',
    labels: {
        singular: 'Запись источника',
        plural: 'Источники данных'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Права и источники'
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'label',
            type: 'text',
            required: true,
            label: 'Обозначение'
        },
        {
            name: 'kind',
            type: 'select',
            required: true,
            label: 'Вид источника',
            options: [
                {
                    label: 'Content API провайдера',
                    value: 'provider_api'
                },
                {
                    label: 'Переданный файл',
                    value: 'file'
                },
                {
                    label: 'Ручная запись редактора',
                    value: 'manual'
                }
            ]
        },
        {
            name: 'reference',
            type: 'text',
            required: true,
            label: 'Ссылка/путь'
        },
        {
            name: 'sha256',
            type: 'text',
            label: 'SHA-256 переданного файла'
        },
        {
            name: 'retrievedAt',
            type: 'date',
            label: 'Дата получения'
        }
    ]
};
const Voices = {
    slug: 'voices',
    labels: {
        singular: 'Озвучка',
        plural: 'Озвучки'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Каталог (общий)',
        description: 'Справочник озвучек. Значения используются в атрибутах плеера only-voice / priority-voice ' + 'строго в том виде, в каком их принимает документированный контракт плеера.'
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            unique: true,
            index: true,
            label: 'URL-код'
        },
        {
            name: 'playerValue',
            type: 'text',
            label: 'Значение для контракта плеера',
            admin: {
                description: 'Заполняется только значением, подтверждённым документацией или ответом провайдера. ' + 'Пусто = озвучка не передаётся в плеер (BLOCKED_INPUT для сценариев, где она требуется).'
            }
        },
        ...provenanceFields
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/comments.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CommentReports",
    ()=>CommentReports,
    "Comments",
    ()=>Comments
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$submit$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/comments/submit.ts [app-rsc] (ecmascript)");
;
;
const Comments = {
    slug: 'comments',
    labels: {
        singular: 'Комментарий',
        plural: 'Комментарии'
    },
    admin: {
        useAsTitle: 'excerpt',
        group: 'Модерация',
        description: 'Очередь модерации: новые комментарии ждут решения и не видны на сайте.',
        defaultColumns: [
            'excerpt',
            'status',
            'targetType',
            'createdAt'
        ]
    },
    access: {
        // Анонимного чтения через REST/GraphQL нет: публичная страница рендерится на
        // сервере через tenantQuery, который обязан указать сайт явно. Иначе открытый
        // /api/comments отдавал бы комментарии всех трёх сайтов сразу.
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        // Создание идёт через серверный endpoint с валидацией и лимитами, не напрямую.
        create: ()=>false,
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('moderator'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    // Единственный путь создания комментария: серверный обработчик с проверками.
    endpoints: [
        {
            path: '/submit',
            method: 'post',
            handler: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$submit$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["submitComment"]
        }
    ],
    indexes: [
        {
            fields: [
                'tenant',
                'targetType',
                'targetId',
                'status'
            ]
        },
        {
            fields: [
                'tenant',
                'status',
                'createdAt'
            ]
        },
        {
            fields: [
                'tenant',
                'authorKey',
                'createdAt'
            ]
        }
    ],
    fields: [
        {
            name: 'targetType',
            type: 'select',
            required: true,
            index: true,
            label: 'Объект обсуждения',
            options: [
                {
                    label: 'Тайтл',
                    value: 'title'
                },
                {
                    label: 'Сезон',
                    value: 'season'
                },
                {
                    label: 'Серия',
                    value: 'episode'
                },
                {
                    label: 'Материал',
                    value: 'post'
                }
            ]
        },
        {
            name: 'targetId',
            type: 'text',
            required: true,
            index: true,
            label: 'ID объекта'
        },
        {
            name: 'targetUrl',
            type: 'text',
            label: 'Ссылка на страницу',
            admin: {
                readOnly: true
            }
        },
        {
            name: 'author',
            type: 'relationship',
            relationTo: 'users',
            label: 'Пользователь'
        },
        {
            name: 'guestName',
            type: 'text',
            label: 'Имя гостя'
        },
        {
            name: 'guestEmail',
            type: 'email',
            label: 'E-mail гостя (не публикуется)',
            // Адрес виден только модератору: публичный API его не отдаёт.
            access: {
                read: ({ req })=>Boolean(req.user),
                update: ()=>false
            }
        },
        {
            name: 'parent',
            type: 'relationship',
            relationTo: 'comments',
            label: 'Ответ на комментарий'
        },
        {
            name: 'root',
            type: 'relationship',
            relationTo: 'comments',
            label: 'Корень ветки',
            index: true
        },
        {
            name: 'depth',
            type: 'number',
            defaultValue: 0,
            min: 0,
            max: 3,
            label: 'Глубина вложенности'
        },
        {
            name: 'body',
            type: 'textarea',
            required: true,
            label: 'Текст (очищенный)'
        },
        {
            name: 'excerpt',
            type: 'text',
            label: 'Начало текста',
            admin: {
                readOnly: true
            }
        },
        {
            name: 'status',
            type: 'select',
            required: true,
            defaultValue: 'pending',
            index: true,
            label: 'Состояние',
            options: [
                {
                    label: 'На модерации',
                    value: 'pending'
                },
                {
                    label: 'Опубликован',
                    value: 'published'
                },
                {
                    label: 'Отклонён',
                    value: 'rejected'
                },
                {
                    label: 'Спам',
                    value: 'spam'
                },
                {
                    label: 'Удалён',
                    value: 'deleted'
                }
            ]
        },
        {
            name: 'moderator',
            type: 'relationship',
            relationTo: 'users',
            label: 'Модератор'
        },
        {
            name: 'moderatedAt',
            type: 'date',
            label: 'Когда обработан'
        },
        {
            name: 'moderatorNote',
            type: 'textarea',
            label: 'Заметка модератора',
            access: {
                read: ({ req })=>Boolean(req.user)
            }
        },
        {
            name: 'reportCount',
            type: 'number',
            defaultValue: 0,
            label: 'Жалоб'
        },
        {
            name: 'authorKey',
            type: 'text',
            index: true,
            label: 'Ключ отправителя',
            // Отпечаток отправителя (не IP) для лимитов частоты. Публично не отдаётся.
            access: {
                read: ({ req })=>Boolean(req.user),
                create: ()=>false,
                update: ()=>false
            },
            admin: {
                readOnly: true,
                description: 'Хэш отправителя для антифлуда. Исходный IP не хранится.'
            }
        },
        {
            name: 'submissionMeta',
            type: 'json',
            label: 'Технические данные отправки',
            // Метаданные анти-абьюза не отдаются публично и хранятся по политике ретенции.
            access: {
                read: ({ req })=>Boolean(req.user),
                update: ()=>false
            }
        }
    ],
    hooks: {
        beforeChange: [
            ({ data })=>{
                if (typeof data?.body === 'string') {
                    data.excerpt = data.body.replace(/\s+/g, ' ').slice(0, 120);
                }
                return data;
            }
        ]
    }
};
const CommentReports = {
    slug: 'comment-reports',
    labels: {
        singular: 'Жалоба',
        plural: 'Жалобы на комментарии'
    },
    admin: {
        useAsTitle: 'reason',
        group: 'Модерация'
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: ()=>false,
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('moderator'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'comment',
            type: 'relationship',
            relationTo: 'comments',
            required: true,
            label: 'Комментарий'
        },
        {
            name: 'reason',
            type: 'select',
            required: true,
            label: 'Причина',
            options: [
                {
                    label: 'Спам',
                    value: 'spam'
                },
                {
                    label: 'Оскорбление',
                    value: 'abuse'
                },
                {
                    label: 'Спойлер',
                    value: 'spoiler'
                },
                {
                    label: 'Другое',
                    value: 'other'
                }
            ]
        },
        {
            name: 'note',
            type: 'textarea',
            label: 'Пояснение'
        },
        {
            name: 'resolved',
            type: 'checkbox',
            defaultValue: false,
            label: 'Обработана'
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/operations.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ImportJobs",
    ()=>ImportJobs,
    "PlayerProfiles",
    ()=>PlayerProfiles,
    "ReleaseEvents",
    ()=>ReleaseEvents
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
const ImportJobs = {
    slug: 'import-jobs',
    labels: {
        singular: 'Задание импорта',
        plural: 'Задания импорта'
    },
    admin: {
        useAsTitle: 'reference',
        group: 'Операции',
        description: 'Журнал обращений к Content API провайдера. Показывает, что именно было запрошено, ' + 'сколько записей создано/обновлено/пропущено и в каком режиме (mock или live).',
        defaultColumns: [
            'reference',
            'mode',
            'status',
            'startedAt'
        ]
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('analyst'),
        create: ()=>false,
        update: ()=>false,
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    indexes: [
        {
            fields: [
                'requestDigest'
            ]
        },
        {
            fields: [
                'status',
                'startedAt'
            ]
        }
    ],
    fields: [
        {
            name: 'reference',
            type: 'text',
            required: true,
            index: true,
            label: 'Идентификатор задания'
        },
        {
            name: 'mode',
            type: 'select',
            required: true,
            label: 'Режим',
            options: [
                {
                    label: 'Фикстуры (mock)',
                    value: 'mock'
                },
                {
                    label: 'Живой Content API',
                    value: 'live'
                }
            ],
            admin: {
                description: 'Production технически отвергает mock: проверка выполняется в адаптере, а не на словах.'
            }
        },
        {
            name: 'status',
            type: 'select',
            required: true,
            label: 'Статус',
            options: [
                {
                    label: 'Выполняется',
                    value: 'running'
                },
                {
                    label: 'Успешно',
                    value: 'succeeded'
                },
                {
                    label: 'Ошибка',
                    value: 'failed'
                },
                {
                    label: 'Заблокировано входными данными',
                    value: 'blocked_input'
                },
                {
                    label: 'Заблокировано правами на контент',
                    value: 'blocked_content_rights'
                }
            ]
        },
        {
            name: 'requestDigest',
            type: 'text',
            required: true,
            label: 'Отпечаток запроса',
            admin: {
                description: 'sha256 нормализованных параметров запроса. Повторный импорт с тем же отпечатком ' + 'обязан быть идемпотентным: те же данные не создают дублей.'
            }
        },
        {
            name: 'startedAt',
            type: 'date',
            required: true,
            label: 'Начало'
        },
        {
            name: 'finishedAt',
            type: 'date',
            label: 'Завершение'
        },
        {
            type: 'row',
            fields: [
                {
                    name: 'created',
                    type: 'number',
                    defaultValue: 0,
                    label: 'Создано'
                },
                {
                    name: 'updated',
                    type: 'number',
                    defaultValue: 0,
                    label: 'Обновлено'
                },
                {
                    name: 'skipped',
                    type: 'number',
                    defaultValue: 0,
                    label: 'Без изменений'
                },
                {
                    name: 'blocked',
                    type: 'number',
                    defaultValue: 0,
                    label: 'Заблокировано'
                }
            ]
        },
        {
            name: 'message',
            type: 'textarea',
            label: 'Сообщение',
            admin: {
                description: 'Текст ошибки после редакции секретов. Токен и заголовки авторизации сюда не попадают.'
            }
        },
        {
            name: 'artifactPath',
            type: 'text',
            label: 'Артефакт запуска'
        }
    ]
};
const ReleaseEvents = {
    slug: 'release-events',
    labels: {
        singular: 'Событие расписания',
        plural: 'Расписание выходов'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Каталог (общий)',
        description: 'Фактические даты выхода эпизодов. Общие для всех сайтов: расписание — это факт, ' + 'а не редакционный материал конкретного сайта.',
        defaultColumns: [
            'label',
            'airsAt',
            'state'
        ]
    },
    access: {
        read: ()=>true,
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    indexes: [
        {
            fields: [
                'airsAt',
                'state'
            ]
        }
    ],
    fields: [
        {
            name: 'label',
            type: 'text',
            required: true,
            label: 'Подпись события'
        },
        {
            name: 'title',
            type: 'relationship',
            relationTo: 'titles',
            required: true,
            index: true,
            label: 'Тайтл'
        },
        {
            name: 'episode',
            type: 'relationship',
            relationTo: 'episodes',
            label: 'Эпизод'
        },
        {
            name: 'airsAt',
            type: 'date',
            required: true,
            index: true,
            label: 'Дата и время выхода (UTC)'
        },
        {
            name: 'state',
            type: 'select',
            required: true,
            defaultValue: 'announced',
            label: 'Состояние',
            options: [
                {
                    label: 'Анонсировано',
                    value: 'announced'
                },
                {
                    label: 'Вышло',
                    value: 'released'
                },
                {
                    label: 'Перенесено',
                    value: 'delayed'
                },
                {
                    label: 'Отменено',
                    value: 'cancelled'
                }
            ]
        },
        {
            name: 'precision',
            type: 'select',
            required: true,
            defaultValue: 'exact',
            label: 'Точность даты',
            options: [
                {
                    label: 'Точные дата и время',
                    value: 'exact'
                },
                {
                    label: 'Только дата',
                    value: 'day'
                },
                {
                    label: 'Неделя',
                    value: 'week'
                },
                {
                    label: 'Неизвестно',
                    value: 'unknown'
                }
            ],
            admin: {
                description: 'Неизвестную дату нельзя показывать как точную: это выдуманный факт.'
            }
        }
    ]
};
const PlayerProfiles = {
    slug: 'player-profiles',
    labels: {
        singular: 'Профиль плеера',
        plural: 'Профили плеера'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Операции',
        description: 'Параметры встраивания плеера для этого сайта. Значения publisher ID и API-токена здесь ' + 'НЕ хранятся: указывается только имя секрета (secret_ref), значение подставляет сервер.'
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название профиля'
        },
        {
            name: 'publisherIdRef',
            type: 'text',
            required: true,
            label: 'Имя секрета с publisher ID',
            admin: {
                description: 'Например PLAYER_PUBLISHER_ID_SITE_A. Само значение в CMS, git, логи и HTML-исходники ' + 'не попадает — сервер подставляет его при рендере.'
            },
            validate: (value)=>typeof value === 'string' && /^[A-Z][A-Z0-9_]{2,63}$/.test(value) ? true : 'Укажите имя секрета в верхнем регистре, а не его значение.'
        },
        {
            name: 'aggregator',
            type: 'select',
            required: true,
            label: 'Агрегатор идентификаторов',
            options: [
                {
                    label: 'kp',
                    value: 'kp'
                },
                {
                    label: 'mali',
                    value: 'mali'
                },
                {
                    label: 'mdl',
                    value: 'mdl'
                }
            ],
            admin: {
                description: 'Только значения из документированного контракта плеера.'
            }
        },
        {
            type: 'row',
            fields: [
                {
                    name: 'showBanner',
                    type: 'checkbox',
                    defaultValue: false,
                    label: 'Показывать баннер плеера'
                },
                {
                    name: 'showVoiceOnly',
                    type: 'checkbox',
                    defaultValue: false,
                    label: 'Режим «только озвучка»'
                }
            ]
        },
        {
            name: 'priorityVoice',
            type: 'relationship',
            relationTo: 'voices',
            label: 'Приоритетная озвучка',
            admin: {
                description: 'Передаётся в плеер только если у озвучки заполнено значение контракта.'
            }
        },
        {
            name: 'contractNote',
            type: 'textarea',
            label: 'Примечание к контракту',
            admin: {
                readOnly: true,
                description: 'disable-licensed="false" в production неизменно и задаётся кодом, а не этой формой. ' + 'Попытка отправить иное значение — BLOCKED_PLAYER_CONTRACT.'
            }
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/collections/tenant-content.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AuditLog",
    ()=>AuditLog,
    "EditorialCollections",
    ()=>EditorialCollections,
    "Media",
    ()=>Media,
    "Pages",
    ()=>Pages,
    "Posts",
    ()=>Posts,
    "Redirects",
    ()=>Redirects,
    "TenantTitles",
    ()=>TenantTitles
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
/**
 * Tenant-scoped контент: публикации, редакционные тексты, SEO, страницы и медиа.
 * Плагин multi-tenant добавляет поле `tenant` и фильтрует выборки; доступ здесь
 * дополнительно ограничен ролями.
 */ const seoFields = [
    {
        type: 'collapsible',
        label: 'SEO',
        admin: {
            initCollapsed: true
        },
        fields: [
            {
                name: 'seoTitle',
                type: 'text',
                label: 'Title страницы',
                admin: {
                    description: 'Если пусто — собирается по шаблону сайта из фактических данных.'
                }
            },
            {
                name: 'seoDescription',
                type: 'textarea',
                label: 'Description',
                admin: {
                    description: 'Описывает то, что реально видно на странице. Не выдумывать факты.'
                }
            },
            {
                name: 'robots',
                type: 'select',
                defaultValue: 'inherit',
                label: 'Индексация',
                options: [
                    {
                        label: 'По правилу сайта',
                        value: 'inherit'
                    },
                    {
                        label: 'Индексировать',
                        value: 'index'
                    },
                    {
                        label: 'Не индексировать (noindex,follow)',
                        value: 'noindex'
                    }
                ]
            },
            {
                name: 'canonicalOverride',
                type: 'text',
                label: 'Canonical (только по решению)',
                admin: {
                    description: 'Пусто = self-canonical. Заполняется только при документированном решении.'
                }
            }
        ]
    }
];
const TenantTitles = {
    slug: 'tenant-titles',
    labels: {
        singular: 'Публикация тайтла',
        plural: 'Публикации тайтлов'
    },
    admin: {
        useAsTitle: 'slug',
        group: 'Контент сайта',
        description: 'Как конкретный тайтл представлен на этом сайте: URL, редакционный текст, SEO.',
        defaultColumns: [
            'slug',
            'title',
            '_status'
        ]
    },
    versions: {
        drafts: {
            autosave: {
                interval: 2000
            },
            schedulePublish: true
        },
        maxPerDoc: 20
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'title',
            type: 'relationship',
            relationTo: 'titles',
            required: true,
            index: true,
            label: 'Тайтл из общего каталога'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            index: true,
            label: 'URL-код на этом сайте',
            validate: (value)=>typeof value === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value) ? true : 'Строчные латинские буквы, цифры и дефис'
        },
        {
            name: 'editorialIntro',
            type: 'textarea',
            label: 'Редакционное вступление сайта',
            admin: {
                description: 'Оригинальный текст редакции этого сайта. Не копия описания провайдера.'
            }
        },
        {
            name: 'editorialAuthor',
            type: 'relationship',
            relationTo: 'users',
            label: 'Автор редакционного текста'
        },
        {
            name: 'highlight',
            type: 'checkbox',
            defaultValue: false,
            label: 'Показывать в подборках на главной'
        },
        ...seoFields
    ]
};
const EditorialCollections = {
    slug: 'editorial-collections',
    labels: {
        singular: 'Подборка',
        plural: 'Подборки'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Контент сайта',
        defaultColumns: [
            'name',
            'slug',
            '_status'
        ]
    },
    versions: {
        drafts: {
            autosave: {
                interval: 2000
            },
            schedulePublish: true
        },
        maxPerDoc: 20
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название подборки'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            index: true,
            label: 'URL-код'
        },
        {
            name: 'intro',
            type: 'textarea',
            label: 'Вступление редакции',
            admin: {
                description: 'Подборка без собственного текста не индексируется.'
            }
        },
        {
            name: 'items',
            type: 'relationship',
            relationTo: 'tenant-titles',
            hasMany: true,
            label: 'Материалы подборки'
        },
        ...seoFields
    ]
};
const Posts = {
    slug: 'posts',
    labels: {
        singular: 'Материал',
        plural: 'Новости и статьи'
    },
    admin: {
        useAsTitle: 'headline',
        group: 'Контент сайта',
        defaultColumns: [
            'headline',
            'slug',
            'publishedAt',
            '_status'
        ]
    },
    versions: {
        drafts: {
            autosave: {
                interval: 2000
            },
            schedulePublish: true
        },
        maxPerDoc: 20
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'headline',
            type: 'text',
            required: true,
            label: 'Заголовок'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            index: true,
            label: 'URL-код'
        },
        {
            name: 'lead',
            type: 'textarea',
            label: 'Лид'
        },
        {
            name: 'body',
            type: 'textarea',
            label: 'Текст материала'
        },
        {
            name: 'author',
            type: 'relationship',
            relationTo: 'users',
            label: 'Автор'
        },
        {
            name: 'publishedAt',
            type: 'date',
            label: 'Дата публикации'
        },
        {
            name: 'cover',
            type: 'upload',
            relationTo: 'media',
            label: 'Обложка'
        },
        ...seoFields
    ]
};
const Pages = {
    slug: 'pages',
    labels: {
        singular: 'Страница',
        plural: 'Страницы'
    },
    admin: {
        useAsTitle: 'name',
        group: 'Контент сайта',
        defaultColumns: [
            'name',
            'slug',
            '_status'
        ]
    },
    versions: {
        drafts: {
            autosave: {
                interval: 2000
            },
            schedulePublish: true
        },
        maxPerDoc: 20
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'name',
            type: 'text',
            required: true,
            label: 'Название'
        },
        {
            name: 'slug',
            type: 'text',
            required: true,
            index: true,
            label: 'URL-код'
        },
        {
            name: 'body',
            type: 'textarea',
            label: 'Текст страницы'
        },
        ...seoFields
    ]
};
const Media = {
    slug: 'media',
    labels: {
        singular: 'Файл',
        plural: 'Медиафайлы'
    },
    admin: {
        group: 'Контент сайта',
        description: 'Загружайте только материалы с подтверждёнными правами.'
    },
    upload: {
        // Каталог загрузок задаётся окружением: он относится к состоянию стенда,
        // а не к исходникам, и не должен попадать в репозиторий.
        staticDir: process.env.MEDIA_DIR ?? 'var/media',
        mimeTypes: [
            'image/png',
            'image/jpeg',
            'image/webp',
            'image/avif'
        ],
        imageSizes: [
            {
                name: 'card',
                width: 400,
                height: 600,
                position: 'centre'
            },
            {
                name: 'wide',
                width: 1200,
                height: 675,
                position: 'centre'
            }
        ]
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'alt',
            type: 'text',
            required: true,
            label: 'Альтернативный текст',
            admin: {
                description: 'Обязателен: без alt материал не публикуется.'
            }
        },
        {
            name: 'rightsRecord',
            type: 'relationship',
            relationTo: 'rights-records',
            label: 'Права на изображение'
        }
    ]
};
const Redirects = {
    slug: 'redirects',
    labels: {
        singular: 'Редирект',
        plural: 'Редиректы'
    },
    admin: {
        useAsTitle: 'from',
        group: 'Контент сайта'
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('editor'),
        delete: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin')
    },
    fields: [
        {
            name: 'from',
            type: 'text',
            required: true,
            index: true,
            label: 'Старый путь'
        },
        {
            name: 'to',
            type: 'text',
            required: true,
            label: 'Новый путь'
        },
        {
            name: 'status',
            type: 'select',
            defaultValue: '301',
            label: 'Код',
            options: [
                {
                    label: '301',
                    value: '301'
                },
                {
                    label: '410',
                    value: '410'
                }
            ]
        }
    ]
};
const AuditLog = {
    slug: 'audit-log',
    labels: {
        singular: 'Запись журнала',
        plural: 'Журнал изменений'
    },
    admin: {
        useAsTitle: 'summary',
        group: 'Служебное',
        defaultColumns: [
            'summary',
            'actor',
            'createdAt'
        ]
    },
    access: {
        read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
        create: ()=>true,
        update: ()=>false,
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
    },
    fields: [
        {
            name: 'summary',
            type: 'text',
            required: true,
            label: 'Что произошло'
        },
        {
            name: 'actor',
            type: 'relationship',
            relationTo: 'users',
            label: 'Кто'
        },
        {
            name: 'collection',
            type: 'text',
            label: 'Коллекция'
        },
        {
            name: 'documentId',
            type: 'text',
            label: 'ID документа'
        },
        {
            name: 'before',
            type: 'json',
            label: 'До'
        },
        {
            name: 'after',
            type: 'json',
            label: 'После'
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/comments/policy.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "FORM_TOKEN_TTL_SECONDS",
    ()=>FORM_TOKEN_TTL_SECONDS,
    "MAX_DEPTH",
    ()=>MAX_DEPTH,
    "MAX_LINKS",
    ()=>MAX_LINKS,
    "MIN_FILL_SECONDS",
    ()=>MIN_FILL_SECONDS,
    "MIN_LENGTH",
    ()=>MIN_LENGTH,
    "countLinks",
    ()=>countLinks,
    "fingerprint",
    ()=>fingerprint,
    "isRejection",
    ()=>isRejection,
    "reject",
    ()=>reject,
    "sanitizeBody",
    ()=>sanitizeBody,
    "signFormToken",
    ()=>signFormToken,
    "validateSubmission",
    ()=>validateSubmission,
    "verifyFormToken",
    ()=>verifyFormToken
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$crypto__$5b$external$5d$__$28$crypto$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/crypto [external] (crypto, cjs)");
;
const MAX_DEPTH = 3;
const MIN_LENGTH = 2;
const MAX_LINKS = 2;
const MIN_FILL_SECONDS = 3;
const FORM_TOKEN_TTL_SECONDS = 3600;
/** Управляющие символы вырезаются: в тексте комментария им делать нечего. */ const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g;
const reject = (code, message)=>({
        code,
        message
    });
const sanitizeBody = (raw)=>raw.replace(/\r\n?/g, '\n').replace(/<[^>]*>/g, ' ').replace(CONTROL_CHARS, '').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
const countLinks = (text)=>(text.match(/https?:\/\/|www\./gi) ?? []).length;
const signFormToken = (secret, payload)=>{
    const body = `${payload.tenant}.${payload.target}.${payload.issuedAt}`;
    const signature = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$crypto__$5b$external$5d$__$28$crypto$2c$__cjs$29$__["createHmac"])('sha256', secret).update(body).digest('base64url');
    return `${body}.${signature}`;
};
const verifyFormToken = (secret, token, expected, now)=>{
    const parts = token.split('.');
    if (parts.length !== 4) return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.');
    const [tenant, target, issuedAtRaw, signature] = parts;
    const body = `${tenant}.${target}.${issuedAtRaw}`;
    const expectedSignature = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$crypto__$5b$external$5d$__$28$crypto$2c$__cjs$29$__["createHmac"])('sha256', secret).update(body).digest('base64url');
    const provided = Buffer.from(signature);
    const computed = Buffer.from(expectedSignature);
    if (provided.length !== computed.length || !(0, __TURBOPACK__imported__module__$5b$externals$5d2f$crypto__$5b$external$5d$__$28$crypto$2c$__cjs$29$__["timingSafeEqual"])(provided, computed)) {
        return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.');
    }
    if (tenant !== expected.tenant || target !== expected.target) {
        // Токен, выданный для другой страницы или другого сайта, не принимается:
        // иначе одну подпись можно переиспользовать по всему приложению.
        return reject('BAD_TOKEN', 'Форма относится к другой странице.');
    }
    const issuedAt = Number(issuedAtRaw);
    if (!Number.isFinite(issuedAt)) return reject('BAD_TOKEN', 'Форма устарела, обновите страницу.');
    if (now - issuedAt > FORM_TOKEN_TTL_SECONDS) {
        return reject('TOKEN_EXPIRED', 'Форма устарела, обновите страницу.');
    }
    if (now - issuedAt < MIN_FILL_SECONDS) {
        return reject('TOO_FAST', 'Слишком быстро. Попробуйте отправить ещё раз через пару секунд.');
    }
    return {
        issuedAt
    };
};
const fingerprint = (secret, ip, userAgent)=>(0, __TURBOPACK__imported__module__$5b$externals$5d2f$crypto__$5b$external$5d$__$28$crypto$2c$__cjs$29$__["createHash"])('sha256').update(`${secret}:${ip}:${userAgent}`).digest('hex').slice(0, 32);
const validateSubmission = (input, limits)=>{
    if (!limits.commentsEnabled) return reject('COMMENTS_DISABLED', 'Комментарии на сайте отключены.');
    if (input.honeypot && input.honeypot.trim() !== '') {
        // Поле-ловушка скрыто от человека; заполнено — значит, заполнял не человек.
        return reject('HONEYPOT', 'Не удалось отправить комментарий.');
    }
    if (!limits.authenticated && !limits.allowGuests) {
        return reject('GUESTS_DISABLED', 'Комментарии доступны только авторизованным пользователям.');
    }
    const body = sanitizeBody(input.body ?? '');
    if (body.length < MIN_LENGTH) return reject('TOO_SHORT', 'Слишком короткий комментарий.');
    if (body.length > limits.maxLength) {
        return reject('TOO_LONG', `Слишком длинный комментарий: максимум ${limits.maxLength} символов.`);
    }
    if (countLinks(body) > MAX_LINKS) {
        return reject('TOO_MANY_LINKS', 'Слишком много ссылок в комментарии.');
    }
    if (!limits.authenticated) {
        const name = (input.guestName ?? '').trim();
        if (name.length < 2 || name.length > 60) {
            return reject('BAD_NAME', 'Укажите имя длиной от 2 до 60 символов.');
        }
        const email = (input.guestEmail ?? '').trim();
        if (email && !/^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(email)) {
            return reject('BAD_EMAIL', 'Проверьте адрес электронной почты.');
        }
    }
    if ((input.parentDepth ?? 0) >= MAX_DEPTH) {
        return reject('TOO_DEEP', 'Слишком глубокая ветка обсуждения.');
    }
    return {
        body
    };
};
const isRejection = (value)=>Boolean(value && typeof value === 'object' && 'code' in value);
}),
"[project]/blueprints/payload-next-multisite/app/src/comments/submit.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "issueFormToken",
    ()=>issueFormToken,
    "submitComment",
    ()=>submitComment
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/lib/tenant-query.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/comments/policy.ts [app-rsc] (ecmascript)");
;
;
/**
 * Приём комментария.
 *
 * Прямое создание через REST закрыто (`create: () => false`), поэтому это
 * единственный путь. Здесь же выполняются лимиты, проверка формы и модерация:
 * если бы создание было открыто, любую из этих проверок можно было бы обойти
 * обычным POST на /api/comments.
 */ const TARGET_TYPES = new Set([
    'title',
    'season',
    'episode',
    'post'
]);
const json = (status, body)=>new Response(JSON.stringify(body), {
        status,
        headers: {
            'content-type': 'application/json; charset=utf-8',
            'cache-control': 'no-store'
        }
    });
const clientIp = (req)=>{
    const forwarded = req.headers.get('x-forwarded-for') ?? '';
    return (forwarded.split(',')[0] ?? '').trim() || req.headers.get('x-real-ip') || 'unknown';
};
const issueFormToken = (secret, tenantId, targetType, targetId, nowSeconds)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["signFormToken"])(secret, {
        tenant: String(tenantId),
        target: `${targetType}:${targetId}`,
        issuedAt: nowSeconds
    });
const submitComment = async (req)=>{
    const secret = process.env.PAYLOAD_SECRET;
    if (!secret) return json(500, {
        error: 'BLOCKED_SECRET: приложение не настроено'
    });
    let input;
    try {
        input = await req.json?.() ?? {};
    } catch  {
        return json(400, {
            error: 'Некорректный запрос.'
        });
    }
    const targetType = String(input.targetType ?? '');
    const targetId = String(input.targetId ?? '');
    if (!TARGET_TYPES.has(targetType) || !targetId) {
        return json(400, {
            error: 'Неизвестный объект обсуждения.'
        });
    }
    let tenant;
    try {
        tenant = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["resolveTenantByHost"])(req.payload, req.headers.get('host'));
    } catch  {
        return json(400, {
            error: 'Сайт не определён.'
        });
    }
    const settings = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(req.payload, {
        collection: 'site-settings',
        tenant,
        depth: 0
    });
    const limits = {
        maxLength: Number(settings?.maxLength ?? 4000),
        allowGuests: tenant.allowGuestComments,
        authenticated: Boolean(req.user),
        commentsEnabled: settings?.commentsEnabled !== false
    };
    const nowSeconds = Math.floor(Date.now() / 1000);
    const tokenCheck = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["verifyFormToken"])(secret, String(input.formToken ?? ''), {
        tenant: String(tenant.id),
        target: `${targetType}:${targetId}`
    }, nowSeconds);
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isRejection"])(tokenCheck)) return json(400, {
        error: tokenCheck.message,
        code: tokenCheck.code
    });
    // Ответ на комментарий обязан быть в том же сайте и на том же объекте:
    // иначе ветку одного сайта можно продолжить с другого.
    let parent = null;
    if (input.parent) {
        parent = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$lib$2f$tenant$2d$query$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantFindOne"])(req.payload, {
            collection: 'comments',
            tenant,
            where: {
                and: [
                    {
                        id: {
                            equals: input.parent
                        }
                    },
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
            depth: 0
        });
        if (!parent) return json(400, {
            error: 'Комментарий, на который вы отвечаете, недоступен.'
        });
    }
    const validation = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["validateSubmission"])({
        body: String(input.body ?? ''),
        guestName: input.guestName ? String(input.guestName) : undefined,
        guestEmail: input.guestEmail ? String(input.guestEmail) : undefined,
        honeypot: input.website ? String(input.website) : undefined,
        parentDepth: parent ? Number(parent.depth ?? 0) + 1 : 0
    }, limits);
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isRejection"])(validation)) return json(400, {
        error: validation.message,
        code: validation.code
    });
    const userAgent = (req.headers.get('user-agent') ?? '').slice(0, 200);
    const authorKey = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$comments$2f$policy$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["fingerprint"])(secret, clientIp(req), userAgent);
    const interval = Number(settings?.minIntervalSeconds ?? 30);
    if (interval > 0) {
        const since = new Date(Date.now() - interval * 1000).toISOString();
        const recent = await req.payload.count({
            collection: 'comments',
            overrideAccess: true,
            where: {
                and: [
                    {
                        tenant: {
                            equals: tenant.id
                        }
                    },
                    {
                        authorKey: {
                            equals: authorKey
                        }
                    },
                    {
                        createdAt: {
                            greater_than: since
                        }
                    }
                ]
            }
        });
        if (recent.totalDocs > 0) {
            return json(429, {
                error: `Подождите ${interval} секунд перед следующим комментарием.`,
                code: 'RATE_LIMIT'
            });
        }
    }
    // Премодерация по умолчанию включена: комментарий не появляется на сайте,
    // пока его не посмотрел модератор.
    const status = settings?.premoderation === false ? 'published' : 'pending';
    const depth = parent ? Number(parent.depth ?? 0) + 1 : 0;
    const root = parent ? parent.root ?? parent.id : undefined;
    const created = await req.payload.create({
        collection: 'comments',
        overrideAccess: true,
        data: {
            tenant: tenant.id,
            targetType,
            targetId,
            targetUrl: String(input.targetUrl ?? '').slice(0, 500),
            author: req.user?.id,
            guestName: req.user ? undefined : String(input.guestName ?? '').trim(),
            guestEmail: req.user ? undefined : String(input.guestEmail ?? '').trim() || undefined,
            parent: parent?.id,
            root,
            depth,
            body: validation.body,
            status,
            authorKey,
            submissionMeta: {
                userAgent,
                receivedAt: new Date().toISOString()
            }
        }
    });
    return json(201, {
        id: created.id,
        status,
        message: status === 'pending' ? 'Комментарий отправлен и появится после проверки модератором.' : 'Комментарий опубликован.'
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/src/globals/index.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "HomeLayout",
    ()=>HomeLayout,
    "Navigation",
    ()=>Navigation,
    "SiteSettings",
    ()=>SiteSettings
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
;
/**
 * «Глобалы» сайта. В мультитенантной установке настоящий Payload global был бы один
 * на все три сайта, поэтому это коллекции, объявленные плагином как isGlobal: по
 * одному документу на тенант. Так настройки Сайта A физически не могут прочитаться
 * при рендере Сайта B.
 */ const globalAccess = {
    read: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tenantScopedAccess"])(),
    create: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
    update: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hasRole"])('site_admin'),
    delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["superAdminOnly"]
};
const SiteSettings = {
    slug: 'site-settings',
    labels: {
        singular: 'Настройки сайта',
        plural: 'Настройки сайта'
    },
    admin: {
        useAsTitle: 'siteName',
        group: 'Настройки сайта',
        description: 'Название, контакты, правила комментариев и SEO-умолчания одного сайта.'
    },
    access: globalAccess,
    fields: [
        {
            name: 'siteName',
            type: 'text',
            required: true,
            label: 'Публичное название сайта',
            admin: {
                description: 'Заполняется из пакета сайта. Пустое поле не заменяется придуманным брендом: ' + 'это BLOCKED_INPUT, а не повод сочинить название.'
            }
        },
        {
            name: 'tagline',
            type: 'text',
            label: 'Короткое описание'
        },
        {
            name: 'seoTitleTemplate',
            type: 'text',
            label: 'Шаблон title',
            admin: {
                description: 'Например: «{page} — {site}». Подставляются только фактические значения страницы.'
            }
        },
        {
            name: 'defaultDescription',
            type: 'textarea',
            label: 'Description по умолчанию'
        },
        {
            name: 'defaultOgImage',
            type: 'upload',
            relationTo: 'media',
            label: 'Картинка для соцсетей'
        },
        {
            type: 'collapsible',
            label: 'Комментарии',
            admin: {
                initCollapsed: false
            },
            fields: [
                {
                    name: 'commentsEnabled',
                    type: 'checkbox',
                    defaultValue: true,
                    label: 'Комментарии включены'
                },
                {
                    name: 'premoderation',
                    type: 'checkbox',
                    defaultValue: true,
                    label: 'Премодерация (комментарий публикуется после проверки)',
                    admin: {
                        description: 'Выключение премодерации — решение владельца сайта, оно фиксируется в пакете сайта.'
                    }
                },
                {
                    name: 'minIntervalSeconds',
                    type: 'number',
                    defaultValue: 30,
                    min: 0,
                    label: 'Минимальный интервал между отправками, сек'
                },
                {
                    name: 'maxLength',
                    type: 'number',
                    defaultValue: 4000,
                    min: 1,
                    label: 'Максимальная длина комментария'
                },
                {
                    name: 'rulesText',
                    type: 'textarea',
                    label: 'Правила комментирования',
                    admin: {
                        description: 'Показывается рядом с формой. Текст собственный, не скопированный.'
                    }
                }
            ]
        },
        {
            type: 'collapsible',
            label: 'Юридические страницы',
            admin: {
                initCollapsed: true
            },
            fields: [
                {
                    name: 'legalPages',
                    type: 'relationship',
                    relationTo: 'pages',
                    hasMany: true,
                    label: 'Страницы'
                },
                {
                    name: 'rightsNotice',
                    type: 'textarea',
                    label: 'Уведомление о правах и источниках',
                    admin: {
                        description: 'Обязательно описывает происхождение материалов и порядок обращения правообладателя.'
                    }
                }
            ]
        }
    ]
};
const Navigation = {
    slug: 'navigation',
    labels: {
        singular: 'Навигация',
        plural: 'Навигация'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Настройки сайта',
        description: 'Меню в шапке и подвале. Ссылки ведут только на страницы этого сайта или явно помеченные внешние.'
    },
    access: globalAccess,
    fields: [
        {
            name: 'label',
            type: 'text',
            defaultValue: 'Навигация',
            label: 'Служебное имя'
        },
        {
            name: 'header',
            type: 'array',
            label: 'Меню в шапке',
            labels: {
                singular: 'Пункт',
                plural: 'Пункты'
            },
            fields: [
                {
                    name: 'title',
                    type: 'text',
                    required: true,
                    label: 'Подпись'
                },
                {
                    name: 'href',
                    type: 'text',
                    required: true,
                    label: 'Адрес'
                },
                {
                    name: 'external',
                    type: 'checkbox',
                    defaultValue: false,
                    label: 'Внешняя ссылка (rel=nofollow noopener)'
                }
            ]
        },
        {
            name: 'footerGroups',
            type: 'array',
            label: 'Колонки в подвале',
            labels: {
                singular: 'Колонка',
                plural: 'Колонки'
            },
            fields: [
                {
                    name: 'title',
                    type: 'text',
                    required: true,
                    label: 'Заголовок колонки'
                },
                {
                    name: 'links',
                    type: 'array',
                    label: 'Ссылки',
                    fields: [
                        {
                            name: 'title',
                            type: 'text',
                            required: true,
                            label: 'Подпись'
                        },
                        {
                            name: 'href',
                            type: 'text',
                            required: true,
                            label: 'Адрес'
                        },
                        {
                            name: 'external',
                            type: 'checkbox',
                            defaultValue: false,
                            label: 'Внешняя ссылка'
                        }
                    ]
                }
            ]
        }
    ]
};
const HomeLayout = {
    slug: 'home-layout',
    labels: {
        singular: 'Главная страница',
        plural: 'Главная страница'
    },
    admin: {
        useAsTitle: 'label',
        group: 'Настройки сайта',
        description: 'Состав и порядок блоков главной. Блоки включаются флажком и переставляются перетаскиванием: ' + 'порядок в списке — это порядок на странице.'
    },
    access: globalAccess,
    fields: [
        {
            name: 'label',
            type: 'text',
            defaultValue: 'Главная',
            label: 'Служебное имя'
        },
        {
            name: 'blocks',
            type: 'blocks',
            label: 'Блоки главной',
            labels: {
                singular: 'Блок',
                plural: 'Блоки'
            },
            blocks: [
                {
                    slug: 'heroSpotlight',
                    labels: {
                        singular: 'Витрина',
                        plural: 'Витрины'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'items',
                            type: 'relationship',
                            relationTo: 'tenant-titles',
                            hasMany: true,
                            label: 'Материалы'
                        }
                    ]
                },
                {
                    slug: 'releaseSchedule',
                    labels: {
                        singular: 'Расписание',
                        plural: 'Расписания'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'days',
                            type: 'number',
                            defaultValue: 7,
                            min: 1,
                            max: 31,
                            label: 'Горизонт, дней'
                        }
                    ]
                },
                {
                    slug: 'latestUpdates',
                    labels: {
                        singular: 'Обновления',
                        plural: 'Обновления'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'limit',
                            type: 'number',
                            defaultValue: 12,
                            min: 1,
                            max: 60,
                            label: 'Сколько показывать'
                        }
                    ]
                },
                {
                    slug: 'editorialPicks',
                    labels: {
                        singular: 'Подборки',
                        plural: 'Подборки'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'collections',
                            type: 'relationship',
                            relationTo: 'editorial-collections',
                            hasMany: true,
                            label: 'Подборки'
                        }
                    ]
                },
                {
                    slug: 'newsFeed',
                    labels: {
                        singular: 'Новости',
                        plural: 'Новости'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'limit',
                            type: 'number',
                            defaultValue: 6,
                            min: 1,
                            max: 30,
                            label: 'Сколько показывать'
                        }
                    ]
                },
                {
                    slug: 'genreRails',
                    labels: {
                        singular: 'Полки по жанрам',
                        plural: 'Полки по жанрам'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'genres',
                            type: 'relationship',
                            relationTo: 'genres',
                            hasMany: true,
                            label: 'Жанры'
                        }
                    ]
                },
                {
                    slug: 'textSection',
                    labels: {
                        singular: 'Текстовый блок',
                        plural: 'Текстовые блоки'
                    },
                    fields: [
                        {
                            name: 'enabled',
                            type: 'checkbox',
                            defaultValue: true,
                            label: 'Показывать'
                        },
                        {
                            name: 'heading',
                            type: 'text',
                            label: 'Заголовок'
                        },
                        {
                            name: 'body',
                            type: 'textarea',
                            label: 'Текст'
                        }
                    ]
                }
            ]
        }
    ]
};
}),
"[project]/blueprints/payload-next-multisite/app/src/hooks/tenant-integrity.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TENANT_SCOPED_SLUGS",
    ()=>TENANT_SCOPED_SLUGS,
    "collectReferences",
    ()=>collectReferences,
    "enforceTenantIntegrity",
    ()=>enforceTenantIntegrity
]);
const TENANT_SCOPED_SLUGS = new Set([
    'tenant-titles',
    'editorial-collections',
    'posts',
    'pages',
    'media',
    'redirects',
    'audit-log',
    'comments',
    'comment-reports',
    'player-profiles',
    'site-settings',
    'navigation',
    'home-layout'
]);
const idOf = (value)=>{
    if (typeof value === 'string' || typeof value === 'number') return value;
    if (value && typeof value === 'object' && 'id' in value) {
        const id = value.id;
        if (typeof id === 'string' || typeof id === 'number') return id;
    }
    return null;
};
/** Значение поля relationship/upload в любой из поддерживаемых Payload форм. */ const collectFieldReferences = (field, value, out)=>{
    if (value === null || value === undefined) return;
    const relationTo = field.relationTo;
    if (Array.isArray(value)) {
        for (const item of value)collectFieldReferences(field, item, out);
        return;
    }
    // Полиморфная связь приходит как { relationTo, value }.
    if (value && typeof value === 'object' && 'relationTo' in value) {
        const polymorphic = value;
        const id = idOf(polymorphic.value);
        if (id !== null) out.push({
            relationTo: polymorphic.relationTo,
            id
        });
        return;
    }
    const id = idOf(value);
    if (id === null) return;
    if (typeof relationTo === 'string') out.push({
        relationTo,
        id
    });
};
const walkFields = (fields, data, out)=>{
    if (!data || typeof data !== 'object') return;
    const record = data;
    for (const field of fields){
        switch(field.type){
            case 'row':
            case 'collapsible':
                walkFields(field.fields, record, out);
                break;
            case 'tabs':
                for (const tab of field.tabs){
                    if ('name' in tab && tab.name) walkFields(tab.fields, record[tab.name], out);
                    else walkFields(tab.fields, record, out);
                }
                break;
            case 'group':
                {
                    const name = 'name' in field ? field.name : undefined;
                    walkFields(field.fields, name ? record[name] : record, out);
                    break;
                }
            case 'array':
                {
                    const rows = record[field.name];
                    if (Array.isArray(rows)) for (const row of rows)walkFields(field.fields, row, out);
                    break;
                }
            case 'blocks':
                {
                    const rows = record[field.name];
                    if (!Array.isArray(rows)) break;
                    for (const row of rows){
                        const blockType = row?.blockType;
                        const block = field.blocks.find((candidate)=>typeof candidate === 'string' ? candidate === blockType : candidate.slug === blockType);
                        if (block && typeof block !== 'string') walkFields(block.fields, row, out);
                    }
                    break;
                }
            case 'relationship':
            case 'upload':
                collectFieldReferences(field, record[field.name], out);
                break;
            default:
                break;
        }
    }
};
const collectReferences = (fields, data)=>{
    const out = [];
    walkFields(fields, data, out);
    return out;
};
const enforceTenantIntegrity = async ({ collection, data, originalDoc, req })=>{
    const tenant = idOf(data?.tenant ?? originalDoc?.tenant);
    if (tenant === null) return data;
    const references = collectReferences(collection.fields, data).filter((reference)=>TENANT_SCOPED_SLUGS.has(reference.relationTo));
    if (references.length === 0) return data;
    const payload = req.payload;
    const seen = new Set();
    for (const reference of references){
        const key = `${reference.relationTo}:${reference.id}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const related = await payload.findByID({
            collection: reference.relationTo,
            id: reference.id,
            depth: 0,
            overrideAccess: true,
            disableErrors: true,
            req
        });
        if (!related) {
            throw new Error(`BLOCKED_INPUT: ссылка на несуществующий документ ${reference.relationTo}#${reference.id}`);
        }
        const relatedTenant = idOf(related.tenant);
        if (String(relatedTenant) !== String(tenant)) {
            throw new Error(`BLOCKED_TENANT_LEAK: ${collection.slug} сайта ${tenant} ссылается на ` + `${reference.relationTo}#${reference.id}, принадлежащий сайту ${relatedTenant}`);
        }
    }
    return data;
};
}),
"[project]/blueprints/payload-next-multisite/app/src/lib/tenant-query.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TenantResolutionError",
    ()=>TenantResolutionError,
    "normalizeHost",
    ()=>normalizeHost,
    "resolveTenantByHost",
    ()=>resolveTenantByHost,
    "tenantCount",
    ()=>tenantCount,
    "tenantFind",
    ()=>tenantFind,
    "tenantFindOne",
    ()=>tenantFindOne,
    "tenantGlobal",
    ()=>tenantGlobal
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$hooks$2f$tenant$2d$integrity$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/hooks/tenant-integrity.ts [app-rsc] (ecmascript)");
;
class TenantResolutionError extends Error {
}
const normalizeHost = (host)=>{
    if (!host) throw new TenantResolutionError('BLOCKED_INPUT: запрос без заголовка Host');
    return host.trim().toLowerCase().split(':')[0];
};
const resolveTenantByHost = async (payload, host)=>{
    const domain = normalizeHost(host);
    const result = await payload.find({
        collection: 'tenants',
        where: {
            domain: {
                equals: domain
            }
        },
        limit: 1,
        depth: 0,
        overrideAccess: true
    });
    const doc = result.docs[0];
    if (!doc) {
        // Неизвестный домен не подставляется «первым попавшимся» сайтом: иначе один
        // сайт отдавался бы под чужим адресом вместе с canonical и данными.
        throw new TenantResolutionError(`BLOCKED_INPUT: домен ${domain} не сопоставлен ни одному сайту`);
    }
    return {
        id: doc.id,
        slug: String(doc.slug ?? ''),
        domain: String(doc.domain ?? ''),
        seoProfile: String(doc.seoProfile ?? ''),
        theme: String(doc.theme ?? ''),
        indexingEnabled: Boolean(doc.indexingEnabled),
        allowGuestComments: Boolean(doc.allowGuestComments)
    };
};
const scoped = (tenant, where)=>{
    const constraint = {
        tenant: {
            equals: tenant.id
        }
    };
    return where ? {
        and: [
            constraint,
            where
        ]
    } : constraint;
};
const assertTenantScoped = (collection)=>{
    if (!__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$hooks$2f$tenant$2d$integrity$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TENANT_SCOPED_SLUGS"].has(collection)) {
        throw new TenantResolutionError(`BLOCKED_INPUT: коллекция ${collection} не привязана к сайту, используйте sharedFind`);
    }
};
const tenantFind = async (payload, args)=>{
    assertTenantScoped(args.collection);
    return payload.find({
        collection: args.collection,
        where: scoped(args.tenant, args.where),
        limit: args.limit ?? 20,
        page: args.page ?? 1,
        sort: args.sort,
        depth: args.depth ?? 1,
        draft: args.draft ?? false,
        overrideAccess: true
    });
};
const tenantFindOne = async (payload, args)=>{
    const result = await tenantFind(payload, {
        ...args,
        limit: 1
    });
    return result.docs[0] ?? null;
};
const tenantCount = async (payload, args)=>{
    assertTenantScoped(args.collection);
    return payload.count({
        collection: args.collection,
        where: scoped(args.tenant, args.where),
        overrideAccess: true
    });
};
const tenantGlobal = async (payload, collection, tenant, depth = 2)=>tenantFindOne(payload, {
        collection,
        tenant,
        depth
    });
}),
"[project]/blueprints/payload-next-multisite/app/src/payload.config.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "sharedSlugs",
    ()=>sharedSlugs,
    "tenantScopedSlugs",
    ()=>tenantScopedSlugs
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$path__$5b$external$5d$__$28$path$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/path [external] (path, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$url__$5b$external$5d$__$28$url$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/url [external] (url, cjs)");
var __TURBOPACK__imported__module__$5b$externals$5d2f40$payloadcms$2f$db$2d$postgres__$5b$external$5d$__$2840$payloadcms$2f$db$2d$postgres$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$db$2d$postgres$29$__ = __turbopack_context__.i("[externals]/@payloadcms/db-postgres [external] (@payloadcms/db-postgres, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/db-postgres)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$richtext$2d$lexical$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/richtext-lexical/dist/index.js [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$languages$2f$ru$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/languages/ru.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$sharp__$5b$external$5d$__$28$sharp$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$sharp$29$__ = __turbopack_context__.i("[externals]/sharp [external] (sharp, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/sharp)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/access/index.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$Tenants$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/Tenants.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$Users$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/Users.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/catalog.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/tenant-content.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$comments$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/comments.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$operations$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/collections/operations.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$globals$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/globals/index.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$hooks$2f$tenant$2d$integrity$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/hooks/tenant-integrity.ts [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f40$payloadcms$2f$db$2d$postgres__$5b$external$5d$__$2840$payloadcms$2f$db$2d$postgres$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$db$2d$postgres$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$richtext$2d$lexical$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$sharp__$5b$external$5d$__$28$sharp$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$sharp$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f40$payloadcms$2f$db$2d$postgres__$5b$external$5d$__$2840$payloadcms$2f$db$2d$postgres$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$db$2d$postgres$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$richtext$2d$lexical$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$sharp__$5b$external$5d$__$28$sharp$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$sharp$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
var __TURBOPACK__import$2e$meta__ = {
    get url () {
        return __turbopack_context__.F("blueprints/payload-next-multisite/app/src/payload.config.ts");
    },
    env: {
        DEV: true,
        PROD: false,
        MODE: "development",
        BASE_URL: "/",
        SSR: true
    }
};
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
;
;
;
;
;
;
;
const dirname = __TURBOPACK__imported__module__$5b$externals$5d2f$path__$5b$external$5d$__$28$path$2c$__cjs$29$__["default"].dirname((0, __TURBOPACK__imported__module__$5b$externals$5d2f$url__$5b$external$5d$__$28$url$2c$__cjs$29$__["fileURLToPath"])(__TURBOPACK__import$2e$meta__.url));
/**
 * Обязательные переменные окружения. Пустое значение не заменяется умолчанием:
 * тихий fallback на слабый секрет или чужую базу — это авария, а не удобство.
 */ const required = (name)=>{
    const value = process.env[name];
    if (!value) {
        throw new Error(`BLOCKED_INPUT: не задана переменная окружения ${name}`);
    }
    return value;
};
/**
 * Коллекции, привязанные к сайту. Всё, чего здесь нет, — общий фактический каталог
 * и служебные журналы: они намеренно НЕ получают поле tenant, чтобы один и тот же
 * тайтл не размножался в трёх рассинхронизированных копиях.
 */ const SCOPED = {
    useTenantAccess: true,
    useBaseFilter: true
};
const SCOPED_GLOBAL = {
    ...SCOPED,
    isGlobal: true
};
const TENANT_SCOPED = {
    'tenant-titles': SCOPED,
    'editorial-collections': SCOPED,
    posts: SCOPED,
    pages: SCOPED,
    media: SCOPED,
    redirects: SCOPED,
    'audit-log': SCOPED,
    comments: SCOPED,
    'comment-reports': SCOPED,
    'player-profiles': SCOPED,
    'site-settings': SCOPED_GLOBAL,
    navigation: SCOPED_GLOBAL,
    'home-layout': SCOPED_GLOBAL
};
const tenantScopedSlugs = Object.keys(TENANT_SCOPED);
const sharedSlugs = [
    'tenants',
    'catalog-media',
    'users',
    'genres',
    'studios',
    'titles',
    'seasons',
    'episodes',
    'voices',
    'rights-records',
    'source-records',
    'import-jobs',
    'release-events'
];
/**
 * Хук целостности ставится централизованно: если добавлять его в каждую коллекцию
 * руками, однажды коллекцию заведут и забудут — и межсайтовая ссылка пройдёт.
 */ const withTenantIntegrity = (collections)=>collections.map((collection)=>{
        if (!(collection.slug in TENANT_SCOPED)) return collection;
        return {
            ...collection,
            hooks: {
                ...collection.hooks,
                beforeChange: [
                    ...collection.hooks?.beforeChange ?? [],
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$hooks$2f$tenant$2d$integrity$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["enforceTenantIntegrity"]
                ]
            }
        };
    });
const __TURBOPACK__default__export__ = (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["buildConfig"])({
    admin: {
        user: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$Users$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Users"].slug,
        meta: {
            titleSuffix: ' — Фабрика сайтов'
        }
    },
    collections: withTenantIntegrity([
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$Tenants$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Tenants"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$Users$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Users"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CatalogMedia"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Genres"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Studios"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Titles"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Seasons"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Episodes"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Voices"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["RightsRecords"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$catalog$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SourceRecords"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TenantTitles"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["EditorialCollections"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Posts"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Pages"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Media"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Redirects"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$tenant$2d$content$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["AuditLog"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$comments$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Comments"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$comments$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CommentReports"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$operations$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ImportJobs"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$operations$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ReleaseEvents"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$collections$2f$operations$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PlayerProfiles"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$globals$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SiteSettings"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$globals$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["Navigation"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$globals$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["HomeLayout"]
    ]),
    db: (0, __TURBOPACK__imported__module__$5b$externals$5d2f40$payloadcms$2f$db$2d$postgres__$5b$external$5d$__$2840$payloadcms$2f$db$2d$postgres$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$db$2d$postgres$29$__["postgresAdapter"])({
        pool: {
            connectionString: required('DATABASE_URI')
        },
        push: process.env.PAYLOAD_DB_PUSH === 'true'
    }),
    editor: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$richtext$2d$lexical$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["lexicalEditor"])(),
    // Админка русская и не переключается на английский по языку браузера:
    // эксплуатационный интерфейс должен быть предсказуемым для редакции.
    i18n: {
        fallbackLanguage: 'ru',
        supportedLanguages: {
            ru: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$languages$2f$ru$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ru"]
        }
    },
    secret: required('PAYLOAD_SECRET'),
    sharp: __TURBOPACK__imported__module__$5b$externals$5d2f$sharp__$5b$external$5d$__$28$sharp$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$sharp$29$__["default"],
    typescript: {
        outputFile: __TURBOPACK__imported__module__$5b$externals$5d2f$path__$5b$external$5d$__$28$path$2c$__cjs$29$__["default"].resolve(dirname, 'payload-types.ts')
    },
    plugins: [
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["multiTenantPlugin"])({
            collections: TENANT_SCOPED,
            tenantsSlug: 'tenants',
            // Полный доступ ко всем сайтам — только у super_admin. Роль проверяется на
            // сервере по документу пользователя, а не по данным из запроса.
            userHasAccessToAllTenants: (user)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$access$2f$index$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isSuperAdmin"])(user),
            tenantField: {
                name: 'tenant'
            },
            tenantsArrayField: {
                includeDefaultField: true,
                arrayFieldName: 'tenants',
                arrayTenantFieldName: 'tenant'
            },
            i18n: {
                translations: {
                    ru: {
                        'nav-tenantSelector-label': 'Сайт',
                        'assign-tenant-button-label': 'Назначить сайт',
                        'assign-tenant-modal-title': 'Назначить сайт для «{{title}}»',
                        'field-assignedTenant-label': 'Назначенный сайт'
                    }
                }
            }
        }),
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["seoPlugin"])({
            collections: [
                'tenant-titles',
                'posts',
                'pages'
            ],
            uploadsCollection: 'media',
            tabbedUI: true
        })
    ]
});
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__13_o0kv._.js.map