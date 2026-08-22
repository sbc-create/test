module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateAccountViewMetadata",
    ()=>generateAccountViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateAccountViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: `${t('authentication:accountOfCurrentUser')}`,
        keywords: `${t('authentication:account')}`,
        serverURL: config.serverURL,
        title: t('authentication:account'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/BrowseByFolder/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateBrowseByFolderMetadata",
    ()=>generateBrowseByFolderMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateBrowseByFolderMetadata = async (args)=>{
    const { config, i18n } = args;
    const title = i18n.t('folder:browseByFolder');
    const description = '';
    const keywords = '';
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        ...config.admin.meta || {},
        description,
        keywords,
        serverURL: config.serverURL,
        title
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CollectionFolders/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateCollectionFolderMetadata",
    ()=>generateCollectionFolderMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
;
const generateCollectionFolderMetadata = async (args)=>{
    const { collectionConfig, config, i18n } = args;
    let title = '';
    const description = '';
    const keywords = '';
    if (collectionConfig) {
        title = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getTranslation"])(collectionConfig.labels.singular, i18n);
    }
    title = `${title ? `${title} ` : title}${i18n.t('folder:folders')}`;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        ...config.admin.meta || {},
        description,
        keywords,
        serverURL: config.serverURL,
        title,
        ...collectionConfig?.admin?.meta || {}
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CollectionTrash/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateCollectionTrashMetadata",
    ()=>generateCollectionTrashMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
;
const generateCollectionTrashMetadata = async (args)=>{
    const { collectionConfig, config, i18n } = args;
    let title = '';
    const description = '';
    const keywords = '';
    if (collectionConfig) {
        title = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getTranslation"])(collectionConfig.labels.plural, i18n);
    }
    title = `${title ? `${title} ` : title}${i18n.t('general:trash')}`;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        ...config.admin.meta || {},
        description,
        keywords,
        serverURL: config.serverURL,
        title,
        ...collectionConfig?.admin?.meta || {}
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CreateFirstUser/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateCreateFirstUserViewMetadata",
    ()=>generateCreateFirstUserViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateCreateFirstUserViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: t('authentication:createFirstUser'),
        keywords: t('general:create'),
        serverURL: config.serverURL,
        title: t('authentication:createFirstUser'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateDashboardViewMetadata",
    ()=>generateDashboardViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateDashboardViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        serverURL: config.serverURL,
        title: t('general:dashboard'),
        ...config.admin.meta,
        openGraph: {
            title: t('general:dashboard'),
            ...config.admin.meta?.openGraph || {}
        }
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Document/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "generateDocumentViewMetadata",
    ()=>generateDocumentViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$getMetaBySegment$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Document/getMetaBySegment.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$getMetaBySegment$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$getMetaBySegment$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
const generateDocumentViewMetadata = async (args)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$getMetaBySegment$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getMetaBySegment"])(args);
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ForgotPassword/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateForgotPasswordViewMetadata",
    ()=>generateForgotPasswordViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateForgotPasswordViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: t('authentication:forgotPassword'),
        keywords: t('authentication:forgotPassword'),
        title: t('authentication:forgotPassword'),
        ...config.admin.meta || {},
        serverURL: config.serverURL
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/List/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateListViewMetadata",
    ()=>generateListViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
;
const generateListViewMetadata = async (args)=>{
    const { collectionConfig, config, i18n } = args;
    let title = '';
    const description = '';
    const keywords = '';
    if (collectionConfig) {
        title = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getTranslation"])(collectionConfig.labels.plural, i18n);
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        ...config.admin.meta || {},
        description,
        keywords,
        serverURL: config.serverURL,
        title,
        ...collectionConfig?.admin?.meta || {}
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Login/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateLoginViewMetadata",
    ()=>generateLoginViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateLoginViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: `${t('authentication:login')}`,
        keywords: `${t('authentication:login')}`,
        serverURL: config.serverURL,
        title: t('authentication:login'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ResetPassword/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateResetPasswordViewMetadata",
    ()=>generateResetPasswordViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateResetPasswordViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: t('authentication:resetPassword'),
        keywords: t('authentication:resetPassword'),
        serverURL: config.serverURL,
        title: t('authentication:resetPassword'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/generateCustomViewMetadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateCustomViewMetadata",
    ()=>generateCustomViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateCustomViewMetadata = async (args)=>{
    const { config, // i18n: { t },
    viewConfig } = args;
    if (!viewConfig) {
        return null;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: `Payload`,
        keywords: `Payload`,
        serverURL: config.serverURL,
        title: 'Payload',
        ...config.admin.meta || {},
        ...viewConfig.meta || {},
        openGraph: {
            title: 'Payload',
            ...config.admin.meta?.openGraph || {},
            ...viewConfig.meta?.openGraph || {}
        }
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/getCustomViewByRoute.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getCustomViewByRoute",
    ()=>getCustomViewByRoute
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$isPathMatchingRoute$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/isPathMatchingRoute.js [app-rsc] (ecmascript)");
;
const getCustomViewByRoute = ({ config, currentRoute: currentRouteWithAdmin })=>{
    const { admin: { components: { views } }, routes: { admin: adminRoute } } = config;
    let viewKey;
    const currentRoute = adminRoute === '/' ? currentRouteWithAdmin : currentRouteWithAdmin.replace(adminRoute, '');
    const foundViewConfig = views && typeof views === 'object' && Object.entries(views).find(([key, view])=>{
        const isMatching = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$isPathMatchingRoute$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isPathMatchingRoute"])({
            currentRoute,
            exact: view.exact,
            path: view.path,
            sensitive: view.sensitive,
            strict: view.strict
        });
        if (isMatching) {
            viewKey = key;
        }
        return isMatching;
    })?.[1] || undefined;
    if (!foundViewConfig) {
        return {
            view: {
                Component: null
            },
            viewConfig: null,
            viewKey: null
        };
    }
    return {
        view: {
            payloadComponent: foundViewConfig.Component
        },
        viewConfig: foundViewConfig,
        viewKey
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "generatePageMetadata",
    ()=>generatePageMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$getNextRequestI18n$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/getNextRequestI18n.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Account$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$BrowseByFolder$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/BrowseByFolder/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CollectionFolders$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CollectionFolders/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CollectionTrash$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CollectionTrash/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CreateFirstUser$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CreateFirstUser/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Document/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$ForgotPassword$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ForgotPassword/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$List$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/List/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Login$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Login/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/NotFound/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$ResetPassword$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ResetPassword/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Unauthorized$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Unauthorized/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Verify$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Verify/metadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$generateCustomViewMetadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/generateCustomViewMetadata.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$getCustomViewByRoute$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/getCustomViewByRoute.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$getNextRequestI18n$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$getNextRequestI18n$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
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
const oneSegmentMeta = {
    'create-first-user': __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CreateFirstUser$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateCreateFirstUserViewMetadata"],
    folders: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$BrowseByFolder$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateBrowseByFolderMetadata"],
    forgot: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$ForgotPassword$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateForgotPasswordViewMetadata"],
    login: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Login$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateLoginViewMetadata"],
    logout: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Unauthorized$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateUnauthorizedViewMetadata"],
    'logout-inactivity': __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Unauthorized$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateUnauthorizedViewMetadata"],
    unauthorized: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Unauthorized$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateUnauthorizedViewMetadata"]
};
const generatePageMetadata = async ({ config: configPromise, params: paramsPromise })=>{
    const config = await configPromise;
    const params = await paramsPromise;
    const folderCollectionSlugs = config.collections.reduce((acc, { slug, folders })=>{
        if (folders) {
            return [
                ...acc,
                slug
            ];
        }
        return acc;
    }, []);
    const segments = Array.isArray(params.segments) ? params.segments : [];
    const currentRoute = `/${segments.join('/')}`;
    const [segmentOne, segmentTwo, segmentThree] = segments;
    const isGlobal = segmentOne === 'globals';
    const isCollection = segmentOne === 'collections';
    const i18n = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$getNextRequestI18n$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getNextRequestI18n"])({
        config
    });
    let meta;
    // TODO: handle custom routes
    const collectionConfig = isCollection && segments.length > 1 && config?.collections?.find((collection)=>collection.slug === segmentTwo);
    const globalConfig = isGlobal && segments.length > 1 && config?.globals?.find((global)=>global.slug === segmentTwo);
    switch(segments.length){
        case 0:
            {
                meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateDashboardViewMetadata"])({
                    config,
                    i18n
                });
                break;
            }
        case 1:
            {
                if (folderCollectionSlugs.length && `/${segmentOne}` === config.admin.routes.browseByFolder) {
                    // --> /:folderCollectionSlug
                    meta = await oneSegmentMeta.folders({
                        config,
                        i18n
                    });
                } else if (segmentOne === 'account') {
                    // --> /account
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Account$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateAccountViewMetadata"])({
                        config,
                        i18n
                    });
                    break;
                } else if (oneSegmentMeta[segmentOne]) {
                    // --> /create-first-user
                    // --> /forgot
                    // --> /login
                    // --> /logout
                    // --> /logout-inactivity
                    // --> /unauthorized
                    meta = await oneSegmentMeta[segmentOne]({
                        config,
                        i18n
                    });
                    break;
                }
                break;
            }
        case 2:
            {
                if (`/${segmentOne}` === config.admin.routes.reset) {
                    // --> /reset/:token
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$ResetPassword$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateResetPasswordViewMetadata"])({
                        config,
                        i18n
                    });
                } else if (folderCollectionSlugs.length && `/${segmentOne}` === config.admin.routes.browseByFolder) {
                    // --> /browse-by-folder/:folderID
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$BrowseByFolder$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateBrowseByFolderMetadata"])({
                        config,
                        i18n
                    });
                } else if (isCollection) {
                    // --> /collections/:collectionSlug
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$List$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateListViewMetadata"])({
                        collectionConfig,
                        config,
                        i18n
                    });
                } else if (isGlobal) {
                    // --> /globals/:globalSlug
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateDocumentViewMetadata"])({
                        config,
                        globalConfig,
                        i18n,
                        params
                    });
                }
                break;
            }
        default:
            {
                if (segmentTwo === 'verify') {
                    // --> /:collectionSlug/verify/:token
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Verify$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateVerifyViewMetadata"])({
                        config,
                        i18n
                    });
                } else if (isCollection) {
                    if (segmentThree === 'trash' && segments.length === 3 && collectionConfig) {
                        // Collection Trash Views
                        // --> /collections/:collectionSlug/trash
                        meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CollectionTrash$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateCollectionTrashMetadata"])({
                            collectionConfig,
                            config,
                            i18n,
                            params
                        });
                    } else if (config.folders && segmentThree === config.folders.slug) {
                        if (folderCollectionSlugs.includes(collectionConfig.slug)) {
                            // Collection Folder Views
                            // --> /collections/:collectionSlug/:folderCollectionSlug
                            // --> /collections/:collectionSlug/:folderCollectionSlug/:id
                            meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$CollectionFolders$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateCollectionFolderMetadata"])({
                                collectionConfig,
                                config,
                                i18n,
                                params
                            });
                        }
                    } else {
                        // Collection Document Views
                        // --> /collections/:collectionSlug/:id
                        // --> /collections/:collectionSlug/:id/versions
                        // --> /collections/:collectionSlug/:id/versions/:version
                        // --> /collections/:collectionSlug/:id/api
                        // --> /collections/:collectionSlug/trash/:id
                        meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateDocumentViewMetadata"])({
                            collectionConfig,
                            config,
                            i18n,
                            params
                        });
                    }
                } else if (isGlobal) {
                    // Global Document Views
                    // --> /globals/:globalSlug/versions
                    // --> /globals/:globalSlug/versions/:version
                    // --> /globals/:globalSlug/api
                    meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Document$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateDocumentViewMetadata"])({
                        config,
                        globalConfig,
                        i18n,
                        params
                    });
                }
                break;
            }
    }
    if (!meta) {
        const { viewConfig, viewKey } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$getCustomViewByRoute$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getCustomViewByRoute"])({
            config,
            currentRoute
        });
        if (viewKey) {
            // Custom Views
            // --> /:path
            meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$generateCustomViewMetadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateCustomViewMetadata"])({
                config,
                i18n,
                viewConfig
            });
        } else {
            meta = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateNotFoundViewMetadata"])({
                config,
                i18n
            });
        }
    }
    return meta;
};
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Unauthorized/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateUnauthorizedViewMetadata",
    ()=>generateUnauthorizedViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateUnauthorizedViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: t('error:unauthorized'),
        keywords: t('error:unauthorized'),
        serverURL: config.serverURL,
        title: t('error:unauthorized'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Verify/metadata.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateVerifyViewMetadata",
    ()=>generateVerifyViewMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/utilities/meta.js [app-rsc] (ecmascript)");
;
const generateVerifyViewMetadata = async ({ config, i18n: { t } })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$utilities$2f$meta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generateMetadata"])({
        description: t('authentication:verifyUser'),
        keywords: t('authentication:verify'),
        serverURL: config.serverURL,
        title: t('authentication:verify'),
        ...config.admin.meta || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/[[...segments]]/not-found.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "generateMetadata",
    ()=>generateMetadata
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/payload.config.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/importMap.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/NotFound/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Root/metadata.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
const generateMetadata = ({ params, searchParams })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Root$2f$metadata$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["generatePageMetadata"])({
        config: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"],
        params,
        searchParams
    });
const NotFound = ({ params, searchParams })=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$NotFound$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["NotFoundPage"])({
        config: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$payload$2e$config$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"],
        params,
        searchParams,
        importMap: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$app$2f28$payload$292f$admin$2f$importMap$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["importMap"]
    });
const __TURBOPACK__default__export__ = NotFound;
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/[[...segments]]/not-found.tsx [app-rsc] (ecmascript, Next.js Server Component)", (function(__turbopack_context__){

__turbopack_context__.n(__turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/app/(payload)/admin/[[...segments]]/not-found.tsx [app-rsc] (ecmascript)"));
}),
];

//# sourceMappingURL=blueprints_payload-next-multisite_app_008ukey._.js.map