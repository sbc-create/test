(globalThis["TURBOPACK"] || (globalThis["TURBOPACK"] = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Banner/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Banner",
    ()=>Banner
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Link/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const baseClass = 'banner';
const Banner = ({ type = 'default', alignIcon = 'right', children, className, icon, onClick, to })=>{
    const classes = [
        baseClass,
        `${baseClass}--type-${type}`,
        className && className,
        to && `${baseClass}--has-link`,
        (to || onClick) && `${baseClass}--has-action`,
        icon && `${baseClass}--has-icon`,
        icon && `${baseClass}--align-icon-${alignIcon}`
    ].filter(Boolean).join(' ');
    let RenderedType = 'div';
    if (onClick && !to) {
        RenderedType = 'button';
    }
    if (to) {
        RenderedType = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Link"];
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(RenderedType, {
        className: classes,
        href: to || null,
        onClick: onClick,
        children: [
            icon && alignIcon === 'left' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                children: icon
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                className: `${baseClass}__content`,
                children: children
            }),
            icon && alignIcon === 'right' && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                children: icon
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Button/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Button",
    ()=>Button,
    "ButtonContents",
    ()=>ButtonContents
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Chevron$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Chevron/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Edit$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Edit/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Link/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Plus$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Plus/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Swap$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Swap/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$X$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/X/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Link/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Popup$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Popup/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Tooltip$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Tooltip/index.js [app-client] (ecmascript)");
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
;
;
const icons = {
    chevron: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Chevron$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ChevronIcon"],
    edit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Edit$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["EditIcon"],
    link: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LinkIcon"],
    plus: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Plus$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PlusIcon"],
    swap: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Swap$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["SwapIcon"],
    x: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$X$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["XIcon"]
};
const baseClass = 'btn';
const ButtonContents = ({ children, icon, showTooltip, tooltip })=>{
    const BuiltInIcon = icons[icon];
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            tooltip && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Tooltip$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"], {
                className: `${baseClass}__tooltip`,
                show: showTooltip,
                children: tooltip
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                className: `${baseClass}__content`,
                children: [
                    children && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                        className: `${baseClass}__label`,
                        children: children
                    }),
                    icon && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                        className: `${baseClass}__icon`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidElement"])(icon) && icon,
                            BuiltInIcon && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(BuiltInIcon, {})
                        ]
                    })
                ]
            })
        ]
    });
};
const Button = (props)=>{
    const { id, type = 'button', 'aria-label': ariaLabel, buttonStyle = 'primary', children, className, disabled, el = 'button', enableSubMenu, extraButtonProps = {}, icon, iconPosition = 'right', iconStyle = 'without-border', margin = true, newTab, onClick, onMouseDown, ref, round, size = 'medium', SubMenuPopupContent, to, tooltip, url } = props;
    const [showTooltip, setShowTooltip] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(false);
    const classes = [
        baseClass,
        className && className,
        icon && `${baseClass}--icon`,
        iconStyle && `${baseClass}--icon-style-${iconStyle}`,
        icon && !children && `${baseClass}--icon-only`,
        size && `${baseClass}--size-${size}`,
        icon && iconPosition && `${baseClass}--icon-position-${iconPosition}`,
        tooltip && `${baseClass}--has-tooltip`,
        !SubMenuPopupContent && `${baseClass}--withoutPopup`,
        !margin && `${baseClass}--no-margin`
    ].filter(Boolean).join(' ');
    function handleClick(event) {
        setShowTooltip(false);
        if (type !== 'submit' && onClick) {
            event.preventDefault();
        }
        if (onClick) {
            onClick(event);
        }
    }
    const styleClasses = [
        buttonStyle && `${baseClass}--style-${buttonStyle}`,
        disabled && `${baseClass}--disabled`,
        round && `${baseClass}--round`,
        SubMenuPopupContent ? `${baseClass}--withPopup` : `${baseClass}--withoutPopup`
    ].filter(Boolean).join(' ');
    const buttonProps = {
        id,
        type,
        'aria-disabled': disabled,
        'aria-label': ariaLabel,
        className: !SubMenuPopupContent ? [
            classes,
            styleClasses
        ].join(' ') : classes,
        disabled,
        onClick: !disabled ? handleClick : undefined,
        onMouseDown: !disabled ? onMouseDown : undefined,
        onPointerEnter: tooltip ? ()=>setShowTooltip(true) : undefined,
        onPointerLeave: tooltip ? ()=>setShowTooltip(false) : undefined,
        rel: newTab ? 'noopener noreferrer' : undefined,
        target: newTab ? '_blank' : undefined,
        title: ariaLabel,
        ...extraButtonProps
    };
    let buttonElement;
    switch(el){
        case 'anchor':
            buttonElement = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("a", {
                ...buttonProps,
                href: !disabled ? url : undefined,
                ref: ref,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ButtonContents, {
                    icon: icon,
                    showTooltip: showTooltip,
                    tooltip: tooltip,
                    children: children
                })
            });
            break;
        case 'link':
            if (disabled) {
                buttonElement = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    ...buttonProps,
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ButtonContents, {
                        icon: icon,
                        showTooltip: showTooltip,
                        tooltip: tooltip,
                        children: children
                    })
                });
            }
            buttonElement = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Link"], {
                ...buttonProps,
                href: to || url,
                prefetch: false,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ButtonContents, {
                    icon: icon,
                    showTooltip: showTooltip,
                    tooltip: tooltip,
                    children: children
                })
            });
            break;
        default:
            const Tag = el // eslint-disable-line no-case-declarations
            ;
            buttonElement = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Tag, {
                ref: ref,
                ...buttonProps,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ButtonContents, {
                    icon: icon,
                    showTooltip: showTooltip,
                    tooltip: tooltip,
                    children: children
                })
            });
            break;
    }
    if (SubMenuPopupContent) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: styleClasses,
            children: [
                buttonElement,
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Popup$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Popup"], {
                    button: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Chevron$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ChevronIcon"], {}),
                    buttonSize: size,
                    className: disabled && !enableSubMenu ? `${baseClass}--popup-disabled` : '',
                    disabled: disabled && !enableSubMenu,
                    horizontalAlign: "right",
                    id: `${id}-popup`,
                    noBackground: true,
                    render: ({ close })=>SubMenuPopupContent({
                            close: ()=>close()
                        }),
                    size: "large",
                    verticalAlign: "bottom"
                })
            ]
        });
    }
    return buttonElement;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Card/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Card",
    ()=>Card
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Button$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Button/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const baseClass = 'card';
const Card = (props)=>{
    const { id, actions, buttonAriaLabel, href, onClick, title, titleAs } = props;
    const classes = [
        baseClass,
        id,
        (onClick || href) && `${baseClass}--has-onclick`
    ].filter(Boolean).join(' ');
    const Tag = titleAs ?? 'div';
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        className: classes,
        id: id,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Tag, {
                className: `${baseClass}__title`,
                children: title
            }),
            actions && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: `${baseClass}__actions`,
                children: actions
            }),
            (onClick || href) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Button$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Button"], {
                "aria-label": buttonAriaLabel,
                buttonStyle: "none",
                className: `${baseClass}__click`,
                el: "link",
                onClick: onClick,
                to: href
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Drawer/index.js [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Drawer",
    ()=>Drawer,
    "DrawerDepthContext",
    ()=>DrawerDepthContext,
    "DrawerDepthProvider",
    ()=>DrawerDepthProvider,
    "DrawerToggler",
    ()=>DrawerToggler,
    "drawerZBase",
    ()=>drawerZBase,
    "formatDrawerSlug",
    ()=>formatDrawerSlug,
    "useDrawerDepth",
    ()=>useDrawerDepth
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$Modal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/Modal/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$useModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/useModal/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$X$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/X/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$Translation$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/providers/Translation/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Gutter$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Gutter/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'drawer';
const drawerZBase = 100;
const formatDrawerSlug = ({ slug, depth })=>`drawer_${depth}_${slug}`;
;
const DrawerToggler = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(4);
    const { slug, children, className, disabled, onClick, ...rest } = t0;
    const { openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$useModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useModal"])();
    let t1;
    if ($[0] !== onClick || $[1] !== openModal || $[2] !== slug) {
        t1 = (e)=>{
            openModal(slug);
            if (typeof onClick === "function") {
                onClick(e);
            }
        };
        $[0] = onClick;
        $[1] = openModal;
        $[2] = slug;
        $[3] = t1;
    } else {
        t1 = $[3];
    }
    const handleClick = t1;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
        className,
        disabled,
        onClick: handleClick,
        type: "button",
        ...rest,
        children
    });
};
const Drawer = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(22);
    const { slug, children, className, gutter: t1, Header, hoverTitle, title } = t0;
    const gutter = t1 === undefined ? true : t1;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$Translation$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const { closeModal, modalState } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$useModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useModal"])();
    const drawerDepth = useDrawerDepth();
    const isOpen = !!modalState[slug]?.isOpen;
    const [animateIn, setAnimateIn] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(isOpen);
    let t2;
    let t3;
    if ($[0] !== isOpen) {
        t2 = ()=>{
            setAnimateIn(isOpen);
        };
        t3 = [
            isOpen
        ];
        $[0] = isOpen;
        $[1] = t2;
        $[2] = t3;
    } else {
        t2 = $[1];
        t3 = $[2];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLayoutEffect"])(t2, t3);
    if (isOpen) {
        const t4 = animateIn && `${baseClass}--is-open`;
        const t5 = drawerDepth > 1 && `${baseClass}--nested`;
        let t6;
        if ($[3] !== className || $[4] !== t4 || $[5] !== t5) {
            t6 = [
                className,
                baseClass,
                t4,
                t5
            ].filter(Boolean);
            $[3] = className;
            $[4] = t4;
            $[5] = t5;
            $[6] = t6;
        } else {
            t6 = $[6];
        }
        const t7 = t6.join(" ");
        const t8 = drawerZBase + drawerDepth;
        let t9;
        if ($[7] !== Header || $[8] !== children || $[9] !== closeModal || $[10] !== drawerDepth || $[11] !== gutter || $[12] !== hoverTitle || $[13] !== slug || $[14] !== t || $[15] !== t7 || $[16] !== t8 || $[17] !== title) {
            let t10;
            if ($[19] !== closeModal || $[20] !== slug) {
                t10 = ()=>closeModal(slug);
                $[19] = closeModal;
                $[20] = slug;
                $[21] = t10;
            } else {
                t10 = $[21];
            }
            t9 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DrawerDepthProvider, {
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$Modal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Modal"], {
                    className: t7,
                    closeOnBlur: false,
                    slug,
                    style: {
                        zIndex: t8
                    },
                    children: [
                        (!drawerDepth || drawerDepth === 1) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                            className: `${baseClass}__blur-bg`
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
                            "aria-label": t("general:close"),
                            className: `${baseClass}__close`,
                            id: `close-drawer__${slug}`,
                            onClick: t10,
                            type: "button"
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                            className: `${baseClass}__content`,
                            style: {
                                width: `calc(100% - (${drawerDepth} * var(--gutter-h)))`
                            },
                            children: [
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                    className: `${baseClass}__blur-bg-content`
                                }),
                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Gutter$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Gutter"], {
                                    className: `${baseClass}__content-children`,
                                    left: gutter,
                                    right: gutter,
                                    children: [
                                        Header,
                                        Header === undefined && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                            className: `${baseClass}__header`,
                                            children: [
                                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("h2", {
                                                    className: `${baseClass}__header__title`,
                                                    title: hoverTitle ? title : null,
                                                    children: title
                                                }),
                                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
                                                    "aria-label": t("general:close"),
                                                    className: `${baseClass}__header__close`,
                                                    id: `close-drawer__${slug}`,
                                                    onClick: ()=>closeModal(slug),
                                                    type: "button",
                                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$X$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["XIcon"], {})
                                                })
                                            ]
                                        }),
                                        children
                                    ]
                                })
                            ]
                        })
                    ]
                })
            });
            $[7] = Header;
            $[8] = children;
            $[9] = closeModal;
            $[10] = drawerDepth;
            $[11] = gutter;
            $[12] = hoverTitle;
            $[13] = slug;
            $[14] = t;
            $[15] = t7;
            $[16] = t8;
            $[17] = title;
            $[18] = t9;
        } else {
            t9 = $[18];
        }
        return t9;
    }
    return null;
};
const DrawerDepthContext = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])(1);
const DrawerDepthProvider = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(3);
    const { children } = t0;
    const parentDepth = useDrawerDepth();
    const depth = parentDepth + 1;
    let t1;
    if ($[0] !== children || $[1] !== depth) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DrawerDepthContext, {
            value: depth,
            children
        });
        $[0] = children;
        $[1] = depth;
        $[2] = t1;
    } else {
        t1 = $[2];
    }
    return t1;
};
const useDrawerDepth = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["use"])(DrawerDepthContext);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Gutter/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Gutter",
    ()=>Gutter
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const baseClass = 'gutter';
const Gutter = (props)=>{
    const { children, className, left = true, negativeLeft = false, negativeRight = false, ref, right = true } = props;
    const shouldPadLeft = left && !negativeLeft;
    const shouldPadRight = right && !negativeRight;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
        className: [
            baseClass,
            shouldPadLeft && `${baseClass}--left`,
            shouldPadRight && `${baseClass}--right`,
            negativeLeft && `${baseClass}--negative-left`,
            negativeRight && `${baseClass}--negative-right`,
            className
        ].filter(Boolean).join(' '),
        ref: ref,
        children: children
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Link/formatUrl.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatUrl",
    ()=>formatUrl,
    "urlQueryToSearchParams",
    ()=>urlQueryToSearchParams
]);
// Format function modified from nodejs
// Copyright Joyent, Inc. and other Node contributors.
//
// Permission is hereby granted, free of charge, to any person obtaining a
// copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to permit
// persons to whom the Software is furnished to do so, subject to the
// following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
// NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
// DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
// OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
// USE OR OTHER DEALINGS IN THE SOFTWARE.
const slashedProtocols = /https?|ftp|gopher|file/;
function stringifyUrlQueryParam(param) {
    if (typeof param === 'string' || typeof param === 'number' && !isNaN(param) || typeof param === 'boolean') {
        return String(param);
    } else {
        return '';
    }
}
function urlQueryToSearchParams(urlQuery) {
    const result = new URLSearchParams();
    Object.entries(urlQuery).forEach(([key, value])=>{
        if (Array.isArray(value)) {
            value.forEach((item)=>result.append(key, stringifyUrlQueryParam(item)));
        } else {
            result.set(key, stringifyUrlQueryParam(value));
        }
    });
    return result;
}
function formatUrl(urlObj) {
    let { auth } = urlObj;
    const { hostname } = urlObj;
    let protocol = urlObj.protocol || '';
    let pathname = urlObj.pathname || '';
    let hash = urlObj.hash || '';
    let query = urlObj.query || '';
    let host = false;
    auth = auth ? encodeURIComponent(auth).replace(/%3A/i, ':') + '@' : '';
    if (urlObj.host) {
        host = auth + urlObj.host;
    } else if (hostname) {
        host = auth + (~hostname.indexOf(':') ? `[${hostname}]` : hostname);
        if (urlObj.port) {
            host += ':' + urlObj.port;
        }
    }
    if (query && typeof query === 'object') {
        query = String(urlQueryToSearchParams(query));
    }
    let search = urlObj.search || query && `?${query}` || '';
    if (protocol && !protocol.endsWith(':')) {
        protocol += ':';
    }
    if (urlObj.slashes || (!protocol || slashedProtocols.test(protocol)) && host !== false) {
        host = '//' + (host || '');
        if (pathname && pathname[0] !== '/') {
            pathname = '/' + pathname;
        }
    } else if (!host) {
        host = '';
    }
    if (hash && hash[0] !== '#') {
        hash = '#' + hash;
    }
    if (search && search[0] !== '?') {
        search = '?' + search;
    }
    pathname = pathname.replace(/[?#]/g, encodeURIComponent);
    search = search.replace('#', '%23');
    return `${protocol}${host}${pathname}${search}${hash}`;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Link/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Link",
    ()=>Link
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/app-dir/link.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$RouteTransition$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/providers/RouteTransition/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$formatUrl$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Link/formatUrl.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const NextLink = 'default' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"] ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].default : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
// Copied from  https://github.com/vercel/next.js/blob/canary/packages/next/src/client/link.tsx#L180-L191
function isModifiedEvent(event) {
    const eventTarget = event.currentTarget;
    const target = eventTarget.getAttribute('target');
    return target && target !== '_self' || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || // triggers resource download
    event.nativeEvent && event.nativeEvent.which === 2;
}
const Link = ({ children, href, onClick, preventDefault = true, ref, replace, scroll, ...rest })=>{
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$RouteTransition$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouteTransition"])();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(NextLink, {
        href: href,
        onClick: (e)=>{
            if (isModifiedEvent(e)) {
                return;
            }
            if (onClick) {
                onClick(e);
            }
            // We need a preventDefault here so that a clicked link doesn't trigger twice,
            // once for default browser navigation and once for startRouteTransition
            if (preventDefault) {
                e.preventDefault();
            }
            const url = typeof href === 'string' ? href : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Link$2f$formatUrl$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatUrl"])(href);
            const navigate = ()=>{
                if (replace) {
                    void router.replace(url, {
                        scroll
                    });
                } else {
                    void router.push(url, {
                        scroll
                    });
                }
            };
            // Call startRouteTransition if available, otherwise navigate directly
            startRouteTransition(navigate);
        },
        ref: ref,
        ...rest,
        children: children
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Locked/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Locked",
    ()=>Locked
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Lock$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Lock/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$Translation$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/providers/Translation/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$isClientUserObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/isClientUserObject.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Tooltip$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Tooltip/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
const baseClass = 'locked';
const Locked = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(8);
    const { className, user } = t0;
    const [hovered, setHovered] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$providers$2f$Translation$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTranslation"])();
    const userToUse = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$isClientUserObject$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isClientUserObject"])(user) ? user.email ?? user.id : t("general:anotherUser");
    let t1;
    if ($[0] !== className) {
        t1 = [
            baseClass,
            className
        ].filter(Boolean);
        $[0] = className;
        $[1] = t1;
    } else {
        t1 = $[1];
    }
    const t2 = t1.join(" ");
    let t3;
    let t4;
    if ($[2] === Symbol.for("react.memo_cache_sentinel")) {
        t3 = ()=>setHovered(true);
        t4 = ()=>setHovered(false);
        $[2] = t3;
        $[3] = t4;
    } else {
        t3 = $[2];
        t4 = $[3];
    }
    const t5 = `${userToUse} ${t("general:isEditing")}`;
    let t6;
    if ($[4] !== hovered || $[5] !== t2 || $[6] !== t5) {
        t6 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: t2,
            onMouseEnter: t3,
            onMouseLeave: t4,
            role: "button",
            tabIndex: 0,
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Tooltip$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Tooltip"], {
                    alignCaret: "left",
                    className: `${baseClass}__tooltip`,
                    position: "top",
                    show: hovered,
                    children: t5
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$icons$2f$Lock$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LockIcon"], {})
            ]
        });
        $[4] = hovered;
        $[5] = t2;
        $[6] = t5;
        $[7] = t6;
    } else {
        t6 = $[7];
    }
    return t6;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Popup/PopupTrigger/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PopupTrigger",
    ()=>PopupTrigger
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const baseClass = 'popup-button';
const PopupTrigger = (props)=>{
    const { active, button, buttonType, className, disabled, noBackground, setActive, size } = props;
    const classes = [
        baseClass,
        className,
        `${baseClass}--${buttonType}`,
        !noBackground && `${baseClass}--background`,
        size && `${baseClass}--size-${size}`,
        disabled && `${baseClass}--disabled`
    ].filter(Boolean).join(' ');
    const handleClick = ()=>{
        setActive(!active, false);
    };
    const handleKeyDown = (e)=>{
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setActive(!active, true);
        }
    };
    if (buttonType === 'none') {
        return null;
    }
    if (buttonType === 'custom') {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: classes,
            onClick: handleClick,
            onKeyDown: handleKeyDown,
            role: "button",
            tabIndex: 0,
            children: button
        });
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
        className: classes,
        disabled: disabled,
        onClick: handleClick,
        onKeyDown: handleKeyDown,
        tabIndex: 0,
        type: "button",
        children: button
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Popup/index.js [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Popup",
    ()=>Popup
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react-dom/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useEffectEvent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/hooks/useEffectEvent.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Popup$2f$PopupTrigger$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Popup/PopupTrigger/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
const baseClass = 'popup';
/**
 * Selector for all elements the browser considers tabbable.
 */ const TABBABLE_SELECTOR = [
    'a[href]',
    'button:not(:disabled)',
    'input:not(:disabled):not([type="hidden"])',
    'select:not(:disabled)',
    'textarea:not(:disabled)',
    '[tabindex]',
    '[contenteditable]:not([contenteditable="false"])',
    'audio[controls]',
    'video[controls]',
    'summary'
].map((s)=>`${s}:not([tabindex="-1"])`).join(', ');
const Popup = (props)=>{
    const { id, button, buttonClassName, buttonSize, buttonType = 'default', caret = true, children, className, disabled, forceOpen, horizontalAlign = 'left', initActive = false, noBackground, onToggleClose, onToggleOpen, portalClassName, render, showOnHover = false, showScrollbar = false, size = 'medium', verticalAlign = 'bottom' } = props;
    const popupRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const triggerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    /**
  * Keeps track of whether the popup was opened via keyboard.
  * This is used to determine whether to autofocus the first element in the popup.
  * If the popup was opened via mouse, we do not want to autofocus the first element.
  */ const openedViaKeyboardRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(false);
    const [mounted, setMounted] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [active, setActiveInternal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(initActive);
    const [isOnTop, setIsOnTop] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(verticalAlign === 'top');
    // Track when component is mounted to avoid SSR/client hydration mismatch
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Popup.useEffect": ()=>{
            setMounted(true);
        }
    }["Popup.useEffect"], []);
    const setActive = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "Popup.useCallback[setActive]": (isActive, viaKeyboard = false)=>{
            if (isActive) {
                openedViaKeyboardRef.current = viaKeyboard;
                onToggleOpen?.(true);
            } else {
                onToggleClose?.();
            }
            setActiveInternal(isActive);
        }
    }["Popup.useCallback[setActive]"], [
        onToggleClose,
        onToggleOpen
    ]);
    // /////////////////////////////////////
    // Position Calculation
    //
    // Calculates and applies popup position relative to trigger.
    // Always checks viewport bounds (for flipping), but only updates
    // styles if the calculated position differs from current position.
    // /////////////////////////////////////
    const updatePosition = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useEffectEvent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffectEvent"])({
        "Popup.useEffectEvent[updatePosition]": ()=>{
            const trigger = triggerRef.current;
            const popup = popupRef.current;
            if (!trigger || !popup) {
                return;
            }
            const triggerRect = trigger.getBoundingClientRect();
            const popupRect = popup.getBoundingClientRect();
            // Gap between the popup and the trigger/viewport edges (in pixels)
            const offset = 10;
            // /////////////////////////////////////
            // Vertical Positioning
            // Calculates the `top` position in absolute page coordinates.
            // Uses `verticalAlign` prop as the preferred direction, but flips
            // to the opposite side if there's not enough viewport space.
            // /////////////////////////////////////
            let top;
            let onTop = verticalAlign === 'top';
            if (verticalAlign === 'bottom') {
                top = triggerRect.bottom + window.scrollY + offset;
                if (triggerRect.bottom + popupRect.height + offset > window.innerHeight) {
                    top = triggerRect.top + window.scrollY - popupRect.height - offset;
                    onTop = true;
                }
            } else {
                top = triggerRect.top + window.scrollY - popupRect.height - offset;
                if (triggerRect.top - popupRect.height - offset < 0) {
                    top = triggerRect.bottom + window.scrollY + offset;
                    onTop = false;
                }
            }
            setIsOnTop(onTop);
            // /////////////////////////////////////
            // Horizontal Positioning
            // Calculates the `left` position based on `horizontalAlign` prop:
            // - 'left': aligns popup's left edge with trigger's left edge
            // - 'right': aligns popup's right edge with trigger's right edge
            // - 'center': centers popup horizontally relative to trigger
            // Then clamps to keep the popup within viewport bounds.
            // /////////////////////////////////////
            let left = horizontalAlign === 'right' ? triggerRect.right - popupRect.width : horizontalAlign === 'center' ? triggerRect.left + triggerRect.width / 2 - popupRect.width / 2 : triggerRect.left;
            left = Math.max(offset, Math.min(left, window.innerWidth - popupRect.width - offset));
            // /////////////////////////////////////
            // Caret Positioning
            // Positions the caret arrow to point at the trigger's horizontal center.
            // Clamps between 12px from edges to prevent caret from overflowing the popup.
            // /////////////////////////////////////
            const triggerCenter = triggerRect.left + triggerRect.width / 2;
            const caretLeft = Math.max(12, Math.min(triggerCenter - left, popupRect.width - 12));
            // /////////////////////////////////////
            // Apply Styles (only if changed)
            // Compares calculated position with current styles to avoid unnecessary
            // DOM updates during scroll. This prevents visual lag by relying on the absolute
            // positioning where possible (popup slightly lags behind when scrolling really fast),
            // while still allowing position changes when needed (e.g., sticky parent, viewport flip).
            // Values are rounded to match browser's CSS precision and avoid false updates.
            // /////////////////////////////////////
            const newTop = `${Math.round(top)}px`;
            const newLeft = `${Math.round(left + window.scrollX)}px`;
            const newCaretLeft = `${Math.round(caretLeft)}px`;
            if (popup.style.top !== newTop) {
                popup.style.top = newTop;
            }
            if (popup.style.left !== newLeft) {
                popup.style.left = newLeft;
            }
            if (popup.style.getPropertyValue('--caret-left') !== newCaretLeft) {
                popup.style.setProperty('--caret-left', newCaretLeft);
            }
        }
    }["Popup.useEffectEvent[updatePosition]"]);
    // /////////////////////////////////////
    // Click Outside Handler
    // Closes popup when clicking outside both the popup and trigger.
    // /////////////////////////////////////
    const handleClickOutside = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useEffectEvent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffectEvent"])({
        "Popup.useEffectEvent[handleClickOutside]": (e)=>{
            const isOutsidePopup = !popupRef.current?.contains(e.target);
            const isOutsideTrigger = !triggerRef.current?.contains(e.target);
            if (isOutsidePopup && isOutsideTrigger) {
                setActive(false);
            }
        }
    }["Popup.useEffectEvent[handleClickOutside]"]);
    // /////////////////////////////////////
    // Keyboard Navigation
    // Handles keyboard interactions when popup is open:
    // - Escape: closes popup and returns focus to trigger
    // - Tab/Shift+Tab: cycles through focusable items with wrapping
    // - ArrowUp/ArrowDown: same as Shift+Tab/Tab for menu-style navigation
    // Focus is managed manually to support elements the browser might skip.
    // /////////////////////////////////////
    const handleKeyDown = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useEffectEvent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffectEvent"])({
        "Popup.useEffectEvent[handleKeyDown]": (e_0)=>{
            const popup_0 = popupRef.current;
            if (!popup_0 || !active) {
                return;
            }
            if (e_0.key === 'Escape') {
                e_0.preventDefault();
                setActive(false);
                triggerRef.current?.querySelector('button, [tabindex="0"]')?.focus();
                return;
            }
            if (e_0.key === 'Tab' || e_0.key === 'ArrowDown' || e_0.key === 'ArrowUp') {
                const focusable = Array.from(popup_0.querySelectorAll(TABBABLE_SELECTOR));
                if (focusable.length === 0) {
                    return;
                }
                e_0.preventDefault();
                const currentIndex = focusable.findIndex({
                    "Popup.useEffectEvent[handleKeyDown].currentIndex": (el)=>el === document.activeElement
                }["Popup.useEffectEvent[handleKeyDown].currentIndex"]);
                const goBackward = e_0.key === 'ArrowUp' || e_0.key === 'Tab' && e_0.shiftKey;
                let nextIndex;
                if (currentIndex === -1) {
                    nextIndex = goBackward ? focusable.length - 1 : 0;
                } else if (goBackward) {
                    nextIndex = currentIndex === 0 ? focusable.length - 1 : currentIndex - 1;
                } else {
                    nextIndex = currentIndex === focusable.length - 1 ? 0 : currentIndex + 1;
                }
                focusable[nextIndex].focus();
            }
        }
    }["Popup.useEffectEvent[handleKeyDown]"]);
    // /////////////////////////////////////
    // Click Handler for Actionable Elements
    // Closes popup when buttons/links inside are clicked (includes Enter/Space activation).
    // /////////////////////////////////////
    const handleActionableClick = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useEffectEvent$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffectEvent"])({
        "Popup.useEffectEvent[handleActionableClick]": (e_1)=>{
            const target = e_1.target;
            // Allow opting out with data-popup-prevent-close attribute on element or ancestor
            if (target.closest('[data-popup-prevent-close]')) {
                return;
            }
            // Check if the clicked element or any ancestor is an actionable element
            const actionable = target.closest('button, a[href], [role="button"], [role="menuitem"]');
            if (actionable && popupRef.current?.contains(actionable)) {
                setActive(false);
            }
        }
    }["Popup.useEffectEvent[handleActionableClick]"]);
    // /////////////////////////////////////
    // Effect: Setup/Teardown position and focus management
    // /////////////////////////////////////
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Popup.useEffect": ()=>{
            if (!active) {
                return;
            }
            const popup_1 = popupRef.current;
            if (!popup_1) {
                return;
            }
            // /////////////////////////////////////
            // Initial Position
            // Calculate and apply popup position immediately on open.
            // /////////////////////////////////////
            updatePosition();
            // /////////////////////////////////////
            // Focus Management
            // When opened via keyboard, autofocus the first focusable button.
            // When opened via mouse, skip autofocus to avoid unwanted highlights.
            // /////////////////////////////////////
            if (openedViaKeyboardRef.current) {
                // Use requestAnimationFrame to ensure DOM is ready.
                requestAnimationFrame({
                    "Popup.useEffect": ()=>{
                        const firstFocusable = popup_1.querySelector(TABBABLE_SELECTOR);
                        firstFocusable?.focus();
                    }
                }["Popup.useEffect"]);
            }
            // /////////////////////////////////////
            // Event Listeners
            // - resize/scroll: recalculate position (only applies styles if changed)
            // - mousedown: detect clicks outside to close
            // - keydown: handle keyboard navigation
            // /////////////////////////////////////
            window.addEventListener('resize', updatePosition);
            window.addEventListener('scroll', updatePosition, {
                capture: true,
                passive: true
            });
            document.addEventListener('mousedown', handleClickOutside);
            document.addEventListener('keydown', handleKeyDown);
            popup_1.addEventListener('click', handleActionableClick);
            return ({
                "Popup.useEffect": ()=>{
                    window.removeEventListener('resize', updatePosition);
                    window.removeEventListener('scroll', updatePosition, {
                        capture: true
                    });
                    document.removeEventListener('mousedown', handleClickOutside);
                    document.removeEventListener('keydown', handleKeyDown);
                    popup_1.removeEventListener('click', handleActionableClick);
                }
            })["Popup.useEffect"];
        }
    }["Popup.useEffect"], [
        active
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Popup.useEffect": ()=>{
            if (forceOpen !== undefined) {
                setActive(forceOpen);
            }
        }
    }["Popup.useEffect"], [
        forceOpen,
        setActive
    ]);
    const Trigger = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Popup$2f$PopupTrigger$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PopupTrigger"], {
        active: active,
        button: button,
        buttonType: buttonType,
        className: buttonClassName,
        disabled: disabled,
        noBackground: noBackground,
        setActive: setActive,
        size: buttonSize
    });
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        className: [
            baseClass,
            className
        ].filter(Boolean).join(' '),
        id: id,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: `${baseClass}__trigger-wrap`,
                ref: triggerRef,
                children: showOnHover ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: `${baseClass}__on-hover-watch`,
                    onMouseEnter: ()=>setActive(true),
                    onMouseLeave: ()=>setActive(false),
                    role: "button",
                    tabIndex: 0,
                    children: Trigger
                }) : Trigger
            }),
            mounted ? // This ensures that components within the popup, like modals, do not unmount when the popup closes.
            // Otherwise, modals opened from the popup will close unexpectedly when clicking within the modal, since
            // that closes the popup due to the click outside handler.
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: active ? [
                    `${baseClass}__content`,
                    `${baseClass}--size-${size}`,
                    isOnTop ? `${baseClass}--v-top` : `${baseClass}--v-bottom`,
                    portalClassName
                ].filter(Boolean).join(' ') : // tests do not accidentally target inactive popups.
                `${baseClass}__hidden-content`,
                "data-popup-id": id || undefined,
                ref: popupRef,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}__scroll-container${showScrollbar ? ` ${baseClass}__scroll-container--show-scrollbar` : ''}`,
                        children: [
                            render?.({
                                close: ()=>setActive(false)
                            }),
                            children
                        ]
                    }),
                    caret && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__caret`
                    })
                ]
            }), document.body) : null
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Tooltip/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Tooltip",
    ()=>Tooltip
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useIntersect$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/hooks/useIntersect.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const Tooltip = (props)=>{
    const { alignCaret = 'center', boundingRef, children, className, delay = 350, position: positionFromProps, show: showFromProps = true, staticPositioning = false } = props;
    const [show, setShow] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(showFromProps);
    const [position, setPosition] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState('top');
    const getTitleAttribute = (content)=>typeof content === 'string' ? content : '';
    const [ref, intersectionEntry] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$hooks$2f$useIntersect$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useIntersect"])({
        root: boundingRef?.current || null,
        rootMargin: '-145px 0px 0px 100px',
        threshold: 0
    }, staticPositioning);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Tooltip.useEffect": ()=>{
            let timerID;
            // do not use the delay on transition-out
            if (delay && showFromProps) {
                timerID = setTimeout({
                    "Tooltip.useEffect": ()=>{
                        setShow(showFromProps);
                    }
                }["Tooltip.useEffect"], delay);
            } else {
                setShow(showFromProps);
            }
            return ({
                "Tooltip.useEffect": ()=>{
                    if (timerID) {
                        clearTimeout(timerID);
                    }
                }
            })["Tooltip.useEffect"];
        }
    }["Tooltip.useEffect"], [
        showFromProps,
        delay
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "Tooltip.useEffect": ()=>{
            if (staticPositioning) {
                return;
            }
            setPosition(intersectionEntry?.isIntersecting ? 'top' : 'bottom');
        }
    }["Tooltip.useEffect"], [
        intersectionEntry,
        staticPositioning
    ]);
    // The first aside is always on top. The purpose of that is that it can reliably be used for the interaction observer (as it's not moving around), to calculate the position of the actual tooltip.
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
        children: [
            !staticPositioning && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("aside", {
                "aria-hidden": "true",
                className: [
                    'tooltip',
                    className,
                    `tooltip--caret-${alignCaret}`,
                    'tooltip--position-top'
                ].filter(Boolean).join(' '),
                ref: ref,
                style: {
                    opacity: '0'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: "tooltip-content",
                    children: children
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("aside", {
                className: [
                    'tooltip',
                    className,
                    show && 'tooltip--show',
                    `tooltip--caret-${alignCaret}`,
                    `tooltip--position-${positionFromProps || position}`
                ].filter(Boolean).join(' '),
                title: getTitleAttribute(children),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: "tooltip-content",
                    children: children
                })
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/hooks/useEffectEvent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useEffectEvent",
    ()=>useEffectEvent
]);
/**

Polyfill taken and modified from https://github.com/bluesky-social/social-app/blob/ce0bf867ff3b50a495d8db242a7f55371bffeadc/src/lib/hooks/useNonReactiveCallback.ts

Copyright 2023–2025 Bluesky PBC

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
const useEffectEvent = 'useEffectEvent' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"] && typeof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffectEvent === 'function' ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffectEvent : (fn)=>{
    // useEffectEvent is not available in older versions of React, so we need to polyfill it
    const ref = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(fn);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useInsertionEffect"])(()=>{
        ref.current = fn;
    }, [
        fn
    ]);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])((...args)=>{
        const latestFn = ref.current;
        return latestFn(...args);
    }, []);
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/hooks/useIntersect.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useIntersect",
    ()=>useIntersect
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
const useIntersect = (t0, disable)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(8);
    const { root: t1, rootMargin: t2, threshold: t3 } = t0 === undefined ? {} : t0;
    const root = t1 === undefined ? null : t1;
    const rootMargin = t2 === undefined ? "0px" : t2;
    const threshold = t3 === undefined ? 0 : t3;
    const [entry, updateEntry] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [node, setNode] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const observer = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(typeof window !== "undefined" && "IntersectionObserver" in window && !disable ? new window.IntersectionObserver({
        "useIntersect.useRef[observer]": (t4)=>{
            const [ent] = t4;
            return updateEntry(ent);
        }
    }["useIntersect.useRef[observer]"], {
        root,
        rootMargin,
        threshold
    }) : null);
    let t5;
    let t6;
    if ($[0] !== disable || $[1] !== node) {
        t5 = ()=>{
            if (disable) {
                return;
            }
            const { current: currentObserver } = observer;
            currentObserver.disconnect();
            if (node) {
                currentObserver.observe(node);
            }
            return ()=>currentObserver.disconnect();
        };
        t6 = [
            node,
            disable
        ];
        $[0] = disable;
        $[1] = node;
        $[2] = t5;
        $[3] = t6;
    } else {
        t5 = $[2];
        t6 = $[3];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t5, t6);
    let t7;
    if ($[4] !== entry || $[5] !== node || $[6] !== setNode) {
        t7 = [
            setNode,
            entry,
            node
        ];
        $[4] = entry;
        $[5] = node;
        $[6] = setNode;
        $[7] = t7;
    } else {
        t7 = $[7];
    }
    return t7;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Chevron/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ChevronIcon",
    ()=>ChevronIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const ChevronIcon = ({ ariaLabel, className, direction, size })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        "aria-label": ariaLabel,
        className: [
            'icon icon--chevron',
            className,
            size && `icon--size-${size}`
        ].filter(Boolean).join(' '),
        height: "100%",
        style: {
            transform: direction === 'left' ? 'rotate(90deg)' : direction === 'right' ? 'rotate(-90deg)' : direction === 'up' ? 'rotate(180deg)' : undefined
        },
        viewBox: "0 0 20 20",
        width: "100%",
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M14 8L10 12L6 8",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Edit/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "EditIcon",
    ()=>EditIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const EditIcon = ({ className })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        className: [
            className,
            'icon icon--edit'
        ].filter(Boolean).join(' '),
        viewBox: "0 0 20 20",
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M9.68531 4.62938H5.2634C4.92833 4.62938 4.60698 4.76248 4.37004 4.99942C4.13311 5.23635 4 5.5577 4 5.89278V14.7366C4 15.0717 4.13311 15.393 4.37004 15.63C4.60698 15.8669 4.92833 16 5.2634 16H14.1072C14.4423 16 14.7636 15.8669 15.0006 15.63C15.2375 15.393 15.3706 15.0717 15.3706 14.7366V10.3147M13.7124 4.39249C13.9637 4.14118 14.3046 4 14.66 4C15.0154 4 15.3562 4.14118 15.6075 4.39249C15.8588 4.6438 16 4.98464 16 5.34004C16 5.69544 15.8588 6.03629 15.6075 6.28759L9.91399 11.9817C9.76399 12.1316 9.57868 12.2413 9.37515 12.3008L7.56027 12.8314C7.50591 12.8472 7.44829 12.8482 7.39344 12.8341C7.33859 12.8201 7.28853 12.7915 7.24849 12.7515C7.20845 12.7115 7.17991 12.6614 7.16586 12.6066C7.15181 12.5517 7.15276 12.4941 7.16861 12.4397L7.69924 10.6249C7.75896 10.4215 7.86888 10.2364 8.01888 10.0866L13.7124 4.39249Z",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Link/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LinkIcon",
    ()=>LinkIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const LinkIcon = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        "aria-hidden": "true",
        className: "graphic link icon icon--link",
        fill: "none",
        focusable: "false",
        height: "20",
        viewBox: "0 0 20 20",
        width: "20",
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M7.99999 13.3333H6.66666C5.78261 13.3333 4.93476 12.9821 4.30964 12.357C3.68452 11.7319 3.33333 10.884 3.33333 9.99999C3.33333 9.11593 3.68452 8.26809 4.30964 7.64297C4.93476 7.01785 5.78261 6.66666 6.66666 6.66666H7.99999M12 6.66666H13.3333C14.2174 6.66666 15.0652 7.01785 15.6904 7.64297C16.3155 8.26809 16.6667 9.11593 16.6667 9.99999C16.6667 10.884 16.3155 11.7319 15.6904 12.357C15.0652 12.9821 14.2174 13.3333 13.3333 13.3333H12M7.33333 9.99999H12.6667",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Lock/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LockIcon",
    ()=>LockIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const LockIcon = ({ className })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("svg", {
        className: [
            'icon icon--lock',
            className
        ].filter(Boolean).join(' '),
        fill: "none",
        height: "20",
        viewBox: "0 0 20 20",
        width: "20",
        xmlns: "http://www.w3.org/2000/svg",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
                className: "stroke",
                d: "M7.5 9.5V7.5C7.5 6.83696 7.76339 6.20107 8.23223 5.73223C8.70107 5.26339 9.33696 5 10 5C10.663 5 11.2989 5.26339 11.7678 5.73223C12.2366 6.20107 12.5 6.83696 12.5 7.5V9.5",
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeOpacity: "1"
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
                className: "stroke",
                d: "M13.5 9.5H6.5C5.94772 9.5 5.5 9.94772 5.5 10.5V14C5.5 14.5523 5.94772 15 6.5 15H13.5C14.0523 15 14.5 14.5523 14.5 14V10.5C14.5 9.94772 14.0523 9.5 13.5 9.5Z",
                stopOpacity: "1",
                strokeLinecap: "round",
                strokeLinejoin: "round"
            })
        ]
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Plus/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PlusIcon",
    ()=>PlusIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const PlusIcon = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        className: "icon icon--plus",
        height: "20",
        viewBox: "0 0 20 20",
        width: "20",
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M5.33333 9.99998H14.6667M9.99999 5.33331V14.6666",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/Swap/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SwapIcon",
    ()=>SwapIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const SwapIcon = ()=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        className: "icon icon--swap",
        viewBox: "0 0 20 20",
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M7.33334 4L4.66667 6.66667M4.66667 6.66667L7.33334 9.33333M4.66667 6.66667H15.3333M12.6667 16L15.3333 13.3333M15.3333 13.3333L12.6667 10.6667M15.3333 13.3333H4.66667",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/icons/X/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "XIcon",
    ()=>XIcon
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
;
const XIcon = ({ className })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("svg", {
        className: [
            className,
            'icon icon--x'
        ].filter(Boolean).join(' '),
        height: 20,
        viewBox: "0 0 20 20",
        width: 20,
        xmlns: "http://www.w3.org/2000/svg",
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("path", {
            className: "stroke",
            d: "M14 6L6 14M6 6L14 14",
            strokeLinecap: "square"
        })
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/providers/RouteTransition/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RouteTransitionProvider",
    ()=>RouteTransitionProvider,
    "useRouteTransition",
    ()=>useRouteTransition
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const RouteTransitionProvider = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    const { children } = t0;
    const [isTransitioning, setIsTransitioning] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useOptimistic"])(false);
    const [transitionProgress, setTransitionProgress] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(0);
    const transitionProgressRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(transitionProgress);
    const timerID = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    let t1;
    if ($[0] === Symbol.for("react.memo_cache_sentinel")) {
        t1 = ()=>{
            timerID.current = setInterval(()=>{
                const newProgress = transitionProgressRef.current + (0.93 - transitionProgressRef.current) * Math.random() * 0.2 * Math.pow(Math.log(1 + (1 - transitionProgressRef.current) * 0.75), 0.75);
                setTransitionProgress(newProgress);
                transitionProgressRef.current = newProgress;
            }, 250);
        };
        $[0] = t1;
    } else {
        t1 = $[0];
    }
    const initiateProgress = t1;
    let t2;
    let t3;
    if ($[1] !== isTransitioning) {
        t2 = ()=>{
            setTransitionProgress(0);
            transitionProgressRef.current = 0;
            if (isTransitioning) {
                initiateProgress();
            } else {
                if (timerID.current) {
                    clearInterval(timerID.current);
                }
            }
        };
        t3 = [
            isTransitioning,
            initiateProgress
        ];
        $[1] = isTransitioning;
        $[2] = t2;
        $[3] = t3;
    } else {
        t2 = $[2];
        t3 = $[3];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t2, t3);
    let t4;
    if ($[4] !== setIsTransitioning) {
        t4 = (callback)=>{
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["startTransition"])(()=>{
                setIsTransitioning(true);
                if (typeof callback === "function") {
                    callback();
                }
            });
        };
        $[4] = setIsTransitioning;
        $[5] = t4;
    } else {
        t4 = $[5];
    }
    const startRouteTransition = t4;
    let t5;
    if ($[6] !== children || $[7] !== isTransitioning || $[8] !== startRouteTransition || $[9] !== transitionProgress) {
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(RouteTransitionContext, {
            value: {
                isTransitioning,
                startRouteTransition,
                transitionProgress
            },
            children
        });
        $[6] = children;
        $[7] = isTransitioning;
        $[8] = startRouteTransition;
        $[9] = transitionProgress;
        $[10] = t5;
    } else {
        t5 = $[10];
    }
    return t5;
};
const RouteTransitionContext = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createContext({
    isTransitioning: false,
    // Default implementation: just call the callback directly (no transition animation)
    startRouteTransition: (callback)=>{
        if (typeof callback === 'function') {
            callback();
        }
    },
    transitionProgress: 0
});
const useRouteTransition = ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].use(RouteTransitionContext);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/providers/Translation/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TranslationProvider",
    ()=>TranslationProvider,
    "useTranslation",
    ()=>useTranslation
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$importDateFNSLocale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/importDateFNSLocale.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$init$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/init.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$en$2d$US$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/en-US.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const Context = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])({
    // Use `any` here to be replaced later with a more specific type when used
    i18n: {
        dateFNS: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$date$2d$fns$2f$locale$2f$en$2d$US$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["enUS"],
        dateFNSKey: 'en-US',
        fallbackLanguage: 'en',
        language: 'en',
        t: (key)=>key,
        translations: {}
    },
    languageOptions: undefined,
    switchLanguage: undefined,
    t: (key)=>undefined
});
const TranslationProvider = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(18);
    const { children, dateFNSKey, fallbackLang, language, languageOptions, switchLanguageServerAction, translations } = t0;
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const [dateFNS, setDateFNS] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    let t1;
    if ($[0] !== translations) {
        t1 = (key, vars)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$init$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["t"])({
                key,
                translations,
                vars
            });
        $[0] = translations;
        $[1] = t1;
    } else {
        t1 = $[1];
    }
    const nextT = t1;
    let t2;
    if ($[2] !== router || $[3] !== switchLanguageServerAction) {
        t2 = async (lang)=>{
            ;
            try {
                await switchLanguageServerAction(lang);
                router.refresh();
            } catch (t3) {
                const error = t3;
                console.error(`Error loading language: "${lang}"`, error);
            }
        };
        $[2] = router;
        $[3] = switchLanguageServerAction;
        $[4] = t2;
    } else {
        t2 = $[4];
    }
    const switchLanguage = t2;
    let t3;
    let t4;
    if ($[5] !== dateFNSKey) {
        t3 = ()=>{
            const loadDateFNS = async ()=>{
                const imported = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$importDateFNSLocale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["importDateFNSLocale"])(dateFNSKey);
                setDateFNS(imported);
            };
            loadDateFNS();
        };
        t4 = [
            dateFNSKey
        ];
        $[5] = dateFNSKey;
        $[6] = t3;
        $[7] = t4;
    } else {
        t3 = $[6];
        t4 = $[7];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t3, t4);
    let t5;
    if ($[8] !== children || $[9] !== dateFNS || $[10] !== dateFNSKey || $[11] !== fallbackLang || $[12] !== language || $[13] !== languageOptions || $[14] !== nextT || $[15] !== switchLanguage || $[16] !== translations) {
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Context, {
            value: {
                i18n: {
                    dateFNS,
                    dateFNSKey,
                    fallbackLanguage: fallbackLang,
                    language,
                    t: nextT,
                    translations
                },
                languageOptions,
                switchLanguage,
                t: nextT
            },
            children
        });
        $[8] = children;
        $[9] = dateFNS;
        $[10] = dateFNSKey;
        $[11] = fallbackLang;
        $[12] = language;
        $[13] = languageOptions;
        $[14] = nextT;
        $[15] = switchLanguage;
        $[16] = translations;
        $[17] = t5;
    } else {
        t5 = $[17];
    }
    return t5;
};
const useTranslation = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["use"])(Context);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/isClientUserObject.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isClientUserObject",
    ()=>isClientUserObject
]);
const isClientUserObject = (user)=>{
    return user && typeof user === 'object';
};
}),
]);

//# sourceMappingURL=0nrf_%40payloadcms_ui_dist_00a7ej3._.js.map