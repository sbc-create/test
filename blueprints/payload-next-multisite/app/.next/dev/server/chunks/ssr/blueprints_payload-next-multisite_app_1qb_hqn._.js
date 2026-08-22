module.exports = [
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

module.exports = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/module.compiled.js [app-ssr] (ecmascript)").vendored['react-ssr'].ReactJsxDevRuntime;
}),
"[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CommentForm",
    ()=>CommentForm
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
'use client';
;
;
const CommentForm = ({ targetType, targetId, targetUrl, formToken, allowGuests, rulesText, maxLength })=>{
    const [state, setState] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])({
        kind: 'idle'
    });
    const onSubmit = async (event)=>{
        event.preventDefault();
        const form = event.currentTarget;
        const data = new FormData(form);
        setState({
            kind: 'sending'
        });
        const response = await fetch('/api/comments/submit', {
            method: 'POST',
            headers: {
                'content-type': 'application/json'
            },
            body: JSON.stringify({
                targetType,
                targetId,
                targetUrl,
                formToken,
                body: data.get('body'),
                guestName: data.get('guestName'),
                guestEmail: data.get('guestEmail'),
                website: data.get('website'),
                parent: data.get('parent') || undefined
            })
        });
        const payload = await response.json().catch(()=>({}));
        if (response.ok) {
            form.reset();
            setState({
                kind: 'done',
                message: payload.message ?? 'Комментарий отправлен.'
            });
        } else {
            setState({
                kind: 'error',
                message: payload.error ?? 'Не удалось отправить комментарий.'
            });
        }
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
        onSubmit: onSubmit,
        style: {
            display: 'grid',
            gap: '0.75rem',
            maxWidth: '70ch'
        },
        children: [
            allowGuests ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["Fragment"], {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                        children: [
                            "Имя",
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "guestName",
                                required: true,
                                minLength: 2,
                                maxLength: 60,
                                style: {
                                    width: '100%',
                                    minHeight: 44
                                }
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                                lineNumber: 67,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                        lineNumber: 65,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0)),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                        children: [
                            "E-mail (не публикуется, необязательно)",
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "guestEmail",
                                type: "email",
                                style: {
                                    width: '100%',
                                    minHeight: 44
                                }
                            }, void 0, false, {
                                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                                lineNumber: 71,
                                columnNumber: 13
                            }, ("TURBOPACK compile-time value", void 0))
                        ]
                    }, void 0, true, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                        lineNumber: 69,
                        columnNumber: 11
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 64,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                "aria-hidden": "true",
                style: {
                    position: 'absolute',
                    left: '-9999px'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                    children: [
                        "Не заполняйте это поле",
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            name: "website",
                            tabIndex: -1,
                            autoComplete: "off"
                        }, void 0, false, {
                            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                            lineNumber: 80,
                            columnNumber: 11
                        }, ("TURBOPACK compile-time value", void 0))
                    ]
                }, void 0, true, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                    lineNumber: 78,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 77,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                children: [
                    "Комментарий",
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("textarea", {
                        name: "body",
                        required: true,
                        minLength: 2,
                        maxLength: maxLength,
                        rows: 5,
                        style: {
                            width: '100%'
                        }
                    }, void 0, false, {
                        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                        lineNumber: 86,
                        columnNumber: 9
                    }, ("TURBOPACK compile-time value", void 0))
                ]
            }, void 0, true, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 84,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "card__meta",
                children: rulesText
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 89,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                    className: "button",
                    type: "submit",
                    disabled: state.kind === 'sending',
                    children: state.kind === 'sending' ? 'Отправляем…' : 'Отправить'
                }, void 0, false, {
                    fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                    lineNumber: 92,
                    columnNumber: 9
                }, ("TURBOPACK compile-time value", void 0))
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 91,
                columnNumber: 7
            }, ("TURBOPACK compile-time value", void 0)),
            state.message ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "notice",
                role: "status",
                children: state.message
            }, void 0, false, {
                fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
                lineNumber: 98,
                columnNumber: 9
            }, ("TURBOPACK compile-time value", void 0)) : null
        ]
    }, void 0, true, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/CommentForm.tsx",
        lineNumber: 62,
        columnNumber: 5
    }, ("TURBOPACK compile-time value", void 0));
};
}),
"[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Player",
    ()=>Player
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react-jsx-dev-runtime.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/server/route-modules/app-page/vendored/ssr/react.js [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/src/player/contract.ts [app-ssr] (ecmascript)");
'use client';
;
;
;
const Player = ({ attributes, scriptUrl, season, episode, unavailableText })=>{
    const hostRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [unavailable, setUnavailable] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    const [failed, setFailed] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useState"])(false);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const host = hostRef.current;
        if (!host) return;
        const element = document.createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PLAYER_ELEMENT"]);
        for (const [name, value] of Object.entries(attributes)){
            if (value !== undefined) element.setAttribute(name, value);
        }
        const onNoData = ()=>setUnavailable(true);
        element.addEventListener('noData', onNoData);
        host.appendChild(element);
        const existing = document.querySelector(`script[data-player-script="${scriptUrl}"]`);
        let script = existing;
        if (!script) {
            script = document.createElement('script');
            script.src = scriptUrl;
            script.async = true;
            script.dataset.playerScript = scriptUrl;
            script.addEventListener('error', ()=>setFailed(true));
            document.head.appendChild(script);
        }
        return ()=>{
            element.removeEventListener('noData', onNoData);
            element.remove();
        };
    }, [
        attributes,
        scriptUrl
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["useEffect"])(()=>{
        const element = hostRef.current?.querySelector(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$src$2f$player$2f$contract$2e$ts__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["PLAYER_ELEMENT"]);
        if (!element) return;
        // Методы вызываются только те, что есть в контракте, и только если плеер их предоставил.
        if (typeof season === 'number' && typeof element.selectSeason === 'function') element.selectSeason(season);
        if (typeof episode === 'number' && typeof element.selectEpisode === 'function') element.selectEpisode(episode);
    }, [
        season,
        episode
    ]);
    if (unavailable || failed) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "notice",
            role: "status",
            children: unavailableText
        }, void 0, false, {
            fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx",
            lineNumber: 73,
            columnNumber: 7
        }, ("TURBOPACK compile-time value", void 0));
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$ssr$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "player-frame",
        ref: hostRef,
        "data-testid": "player-host"
    }, void 0, false, {
        fileName: "[project]/blueprints/payload-next-multisite/app/src/components/Player.tsx",
        lineNumber: 79,
        columnNumber: 10
    }, ("TURBOPACK compile-time value", void 0));
};
}),
"[project]/blueprints/payload-next-multisite/app/src/player/contract.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
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
];

//# sourceMappingURL=blueprints_payload-next-multisite_app_1qb_hqn._.js.map