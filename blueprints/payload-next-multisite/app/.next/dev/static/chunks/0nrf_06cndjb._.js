(globalThis["TURBOPACK"] || (globalThis["TURBOPACK"] = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/extends.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>_extends
]);
function _extends() {
    return _extends = ("TURBOPACK compile-time truthy", 1) ? Object.assign.bind() : "TURBOPACK unreachable", _extends.apply(null, arguments);
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/inheritsLoose.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>_inheritsLoose
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$setPrototypeOf$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/setPrototypeOf.js [app-client] (ecmascript)");
;
function _inheritsLoose(t, o) {
    t.prototype = Object.create(o.prototype), t.prototype.constructor = t, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$setPrototypeOf$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(t, o);
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/objectWithoutPropertiesLoose.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>_objectWithoutPropertiesLoose
]);
function _objectWithoutPropertiesLoose(r, e) {
    if (null == r) return {};
    var t = {};
    for(var n in r)if (({}).hasOwnProperty.call(r, n)) {
        if (-1 !== e.indexOf(n)) continue;
        t[n] = r[n];
    }
    return t;
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/setPrototypeOf.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>_setPrototypeOf
]);
function _setPrototypeOf(t, e) {
    return _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function(t, e) {
        return t.__proto__ = e, t;
    }, _setPrototypeOf(t, e);
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/accessibility/dist/accessibility.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "HiddenText",
    ()=>HiddenText,
    "LiveRegion",
    ()=>LiveRegion,
    "useAnnouncement",
    ()=>useAnnouncement
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
const hiddenStyles = {
    display: 'none'
};
function HiddenText(_ref) {
    let { id, value } = _ref;
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
        id: id,
        style: hiddenStyles
    }, value);
}
function LiveRegion(_ref) {
    let { id, announcement, ariaLiveType = "assertive" } = _ref;
    // Hide element visually but keep it readable by screen readers
    const visuallyHidden = {
        position: 'fixed',
        top: 0,
        left: 0,
        width: 1,
        height: 1,
        margin: -1,
        border: 0,
        padding: 0,
        overflow: 'hidden',
        clip: 'rect(0 0 0 0)',
        clipPath: 'inset(100%)',
        whiteSpace: 'nowrap'
    };
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
        id: id,
        style: visuallyHidden,
        role: "status",
        "aria-live": ariaLiveType,
        "aria-atomic": true
    }, announcement);
}
function useAnnouncement() {
    const [announcement, setAnnouncement] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const announce = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useAnnouncement.useCallback[announce]": (value)=>{
            if (value != null) {
                setAnnouncement(value);
            }
        }
    }["useAnnouncement.useCallback[announce]"], []);
    return {
        announce,
        announcement
    };
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/utilities/dist/utilities.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CSS",
    ()=>CSS,
    "add",
    ()=>add,
    "canUseDOM",
    ()=>canUseDOM,
    "findFirstFocusableNode",
    ()=>findFirstFocusableNode,
    "getEventCoordinates",
    ()=>getEventCoordinates,
    "getOwnerDocument",
    ()=>getOwnerDocument,
    "getWindow",
    ()=>getWindow,
    "hasViewportRelativeCoordinates",
    ()=>hasViewportRelativeCoordinates,
    "isDocument",
    ()=>isDocument,
    "isHTMLElement",
    ()=>isHTMLElement,
    "isKeyboardEvent",
    ()=>isKeyboardEvent,
    "isNode",
    ()=>isNode,
    "isSVGElement",
    ()=>isSVGElement,
    "isTouchEvent",
    ()=>isTouchEvent,
    "isWindow",
    ()=>isWindow,
    "subtract",
    ()=>subtract,
    "useCombinedRefs",
    ()=>useCombinedRefs,
    "useEvent",
    ()=>useEvent,
    "useInterval",
    ()=>useInterval,
    "useIsomorphicLayoutEffect",
    ()=>useIsomorphicLayoutEffect,
    "useLatestValue",
    ()=>useLatestValue,
    "useLazyMemo",
    ()=>useLazyMemo,
    "useNodeRef",
    ()=>useNodeRef,
    "usePrevious",
    ()=>usePrevious,
    "useUniqueId",
    ()=>useUniqueId
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
function useCombinedRefs() {
    for(var _len = arguments.length, refs = new Array(_len), _key = 0; _key < _len; _key++){
        refs[_key] = arguments[_key];
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useCombinedRefs.useMemo": ()=>({
                "useCombinedRefs.useMemo": (node)=>{
                    refs.forEach({
                        "useCombinedRefs.useMemo": (ref)=>ref(node)
                    }["useCombinedRefs.useMemo"]);
                }
            })["useCombinedRefs.useMemo"]
    }["useCombinedRefs.useMemo"], refs);
}
// https://github.com/facebook/react/blob/master/packages/shared/ExecutionEnvironment.js
const canUseDOM = typeof window !== 'undefined' && typeof window.document !== 'undefined' && typeof window.document.createElement !== 'undefined';
function isWindow(element) {
    const elementString = Object.prototype.toString.call(element);
    return elementString === '[object Window]' || // In Electron context the Window object serializes to [object global]
    elementString === '[object global]';
}
function isNode(node) {
    return 'nodeType' in node;
}
function getWindow(target) {
    var _target$ownerDocument, _target$ownerDocument2;
    if (!target) {
        return window;
    }
    if (isWindow(target)) {
        return target;
    }
    if (!isNode(target)) {
        return window;
    }
    return (_target$ownerDocument = (_target$ownerDocument2 = target.ownerDocument) == null ? void 0 : _target$ownerDocument2.defaultView) != null ? _target$ownerDocument : window;
}
function isDocument(node) {
    const { Document } = getWindow(node);
    return node instanceof Document;
}
function isHTMLElement(node) {
    if (isWindow(node)) {
        return false;
    }
    return node instanceof getWindow(node).HTMLElement;
}
function isSVGElement(node) {
    return node instanceof getWindow(node).SVGElement;
}
function getOwnerDocument(target) {
    if (!target) {
        return document;
    }
    if (isWindow(target)) {
        return target.document;
    }
    if (!isNode(target)) {
        return document;
    }
    if (isDocument(target)) {
        return target;
    }
    if (isHTMLElement(target) || isSVGElement(target)) {
        return target.ownerDocument;
    }
    return document;
}
/**
 * A hook that resolves to useEffect on the server and useLayoutEffect on the client
 * @param callback {function} Callback function that is invoked when the dependencies of the hook change
 */ const useIsomorphicLayoutEffect = canUseDOM ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLayoutEffect"] : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"];
function useEvent(handler) {
    const handlerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(handler);
    useIsomorphicLayoutEffect({
        "useEvent.useIsomorphicLayoutEffect": ()=>{
            handlerRef.current = handler;
        }
    }["useEvent.useIsomorphicLayoutEffect"]);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useEvent.useCallback": function() {
            for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
                args[_key] = arguments[_key];
            }
            return handlerRef.current == null ? void 0 : handlerRef.current(...args);
        }
    }["useEvent.useCallback"], []);
}
function useInterval() {
    const intervalRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const set = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useInterval.useCallback[set]": (listener, duration)=>{
            intervalRef.current = setInterval(listener, duration);
        }
    }["useInterval.useCallback[set]"], []);
    const clear = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useInterval.useCallback[clear]": ()=>{
            if (intervalRef.current !== null) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
        }
    }["useInterval.useCallback[clear]"], []);
    return [
        set,
        clear
    ];
}
function useLatestValue(value, dependencies) {
    if (dependencies === void 0) {
        dependencies = [
            value
        ];
    }
    const valueRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(value);
    useIsomorphicLayoutEffect({
        "useLatestValue.useIsomorphicLayoutEffect": ()=>{
            if (valueRef.current !== value) {
                valueRef.current = value;
            }
        }
    }["useLatestValue.useIsomorphicLayoutEffect"], dependencies);
    return valueRef;
}
function useLazyMemo(callback, dependencies) {
    const valueRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])();
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useLazyMemo.useMemo": ()=>{
            const newValue = callback(valueRef.current);
            valueRef.current = newValue;
            return newValue;
        }
    }["useLazyMemo.useMemo"], [
        ...dependencies
    ]);
}
function useNodeRef(onChange) {
    const onChangeHandler = useEvent(onChange);
    const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const setNodeRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useNodeRef.useCallback[setNodeRef]": (element)=>{
            if (element !== node.current) {
                onChangeHandler == null ? void 0 : onChangeHandler(element, node.current);
            }
            node.current = element;
        }
    }["useNodeRef.useCallback[setNodeRef]"], []);
    return [
        node,
        setNodeRef
    ];
}
function usePrevious(value) {
    const ref = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "usePrevious.useEffect": ()=>{
            ref.current = value;
        }
    }["usePrevious.useEffect"], [
        value
    ]);
    return ref.current;
}
let ids = {};
function useUniqueId(prefix, value) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useUniqueId.useMemo": ()=>{
            if (value) {
                return value;
            }
            const id = ids[prefix] == null ? 0 : ids[prefix] + 1;
            ids[prefix] = id;
            return prefix + "-" + id;
        }
    }["useUniqueId.useMemo"], [
        prefix,
        value
    ]);
}
function createAdjustmentFn(modifier) {
    return function(object) {
        for(var _len = arguments.length, adjustments = new Array(_len > 1 ? _len - 1 : 0), _key = 1; _key < _len; _key++){
            adjustments[_key - 1] = arguments[_key];
        }
        return adjustments.reduce((accumulator, adjustment)=>{
            const entries = Object.entries(adjustment);
            for (const [key, valueAdjustment] of entries){
                const value = accumulator[key];
                if (value != null) {
                    accumulator[key] = value + modifier * valueAdjustment;
                }
            }
            return accumulator;
        }, {
            ...object
        });
    };
}
const add = /*#__PURE__*/ createAdjustmentFn(1);
const subtract = /*#__PURE__*/ createAdjustmentFn(-1);
function hasViewportRelativeCoordinates(event) {
    return 'clientX' in event && 'clientY' in event;
}
function isKeyboardEvent(event) {
    if (!event) {
        return false;
    }
    const { KeyboardEvent } = getWindow(event.target);
    return KeyboardEvent && event instanceof KeyboardEvent;
}
function isTouchEvent(event) {
    if (!event) {
        return false;
    }
    const { TouchEvent } = getWindow(event.target);
    return TouchEvent && event instanceof TouchEvent;
}
/**
 * Returns the normalized x and y coordinates for mouse and touch events.
 */ function getEventCoordinates(event) {
    if (isTouchEvent(event)) {
        if (event.touches && event.touches.length) {
            const { clientX: x, clientY: y } = event.touches[0];
            return {
                x,
                y
            };
        } else if (event.changedTouches && event.changedTouches.length) {
            const { clientX: x, clientY: y } = event.changedTouches[0];
            return {
                x,
                y
            };
        }
    }
    if (hasViewportRelativeCoordinates(event)) {
        return {
            x: event.clientX,
            y: event.clientY
        };
    }
    return null;
}
const CSS = /*#__PURE__*/ Object.freeze({
    Translate: {
        toString (transform) {
            if (!transform) {
                return;
            }
            const { x, y } = transform;
            return "translate3d(" + (x ? Math.round(x) : 0) + "px, " + (y ? Math.round(y) : 0) + "px, 0)";
        }
    },
    Scale: {
        toString (transform) {
            if (!transform) {
                return;
            }
            const { scaleX, scaleY } = transform;
            return "scaleX(" + scaleX + ") scaleY(" + scaleY + ")";
        }
    },
    Transform: {
        toString (transform) {
            if (!transform) {
                return;
            }
            return [
                CSS.Translate.toString(transform),
                CSS.Scale.toString(transform)
            ].join(' ');
        }
    },
    Transition: {
        toString (_ref) {
            let { property, duration, easing } = _ref;
            return property + " " + duration + "ms " + easing;
        }
    }
});
const SELECTOR = 'a,frame,iframe,input:not([type=hidden]):not(:disabled),select:not(:disabled),textarea:not(:disabled),button:not(:disabled),*[tabindex]';
function findFirstFocusableNode(element) {
    if (element.matches(SELECTOR)) {
        return element;
    }
    return element.querySelector(SELECTOR);
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/Modal/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Modal",
    ()=>Modal
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$asModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/asModal/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const _Modal = (props)=>{
    const { children } = props;
    if (children) {
        if (typeof children === 'function') {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                children: children(props)
            });
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: children
        });
    }
    return null;
};
const Modal = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$asModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["asModal"])(_Modal);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/ModalProvider/context.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ModalContext",
    ()=>ModalContext
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
const ModalContext = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])({});
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/ModalProvider/generateTransitionClasses.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateTransitionClasses",
    ()=>generateTransitionClasses
]);
const generateTransitionClasses = (baseClass)=>{
    if (baseClass) {
        return {
            appear: `${baseClass}--appear`,
            appearActive: `${baseClass}--appearActive`,
            appearDone: `${baseClass}--appearDone`,
            enter: `${baseClass}--enter`,
            enterActive: `${baseClass}--enterActive`,
            enterDone: `${baseClass}--enterDone`,
            exit: `${baseClass}--exit`,
            exitActive: `${baseClass}--exitActive`,
            exitDone: `${baseClass}--exitDone`
        };
    }
    return {};
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/asModal/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "asModal",
    ()=>asModal,
    "itemBaseClass",
    ()=>itemBaseClass
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react-dom/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$CSSTransition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__CSSTransition$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/CSSTransition.js [app-client] (ecmascript) <export default as CSSTransition>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$useModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/useModal/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$ModalProvider$2f$generateTransitionClasses$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/ModalProvider/generateTransitionClasses.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$focus$2d$trap$2f$dist$2f$focus$2d$trap$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/focus-trap/dist/focus-trap.esm.js [app-client] (ecmascript)");
'use client';
var __rest = ("TURBOPACK compile-time value", void 0) && ("TURBOPACK compile-time value", void 0).__rest || function(s, e) {
    var t = {};
    for(var p in s)if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function") for(var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++){
        if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
    }
    return t;
};
;
;
;
;
;
;
;
const itemBaseClass = 'modal-item';
const asModal = (ModalComponent, slugFromArg)=>{
    const ModalWrap = (props)=>{
        const modal = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$useModal$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useModal"])();
        const modalRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
        const [layTrap, setLayTrap] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
        const trapHasBeenLayed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(false);
        const [trap, setTrap] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
        const { modalState, classPrefix: classPrefixFromContext, containerRef, transTime, setCloseOnBlur, setBodyScrollLock, openModal } = modal;
        const { className, htmlElement: Tag = 'dialog', slug: slugFromProp = '', closeOnBlur = true, lockBodyScroll = true, // autoFocus: true,
        // trapFocus: true,
        // returnFocus: true,
        classPrefix: classPrefixFromProps, onEnter, onEntering, onEntered, onExit, onExiting, onExited, openOnInit, trapFocus = true, focusTrapOptions = {} } = props, rest = __rest(props, [
            "className",
            "htmlElement",
            "slug",
            "closeOnBlur",
            "lockBodyScroll",
            "classPrefix",
            "onEnter",
            "onEntering",
            "onEntered",
            "onExit",
            "onExiting",
            "onExited",
            "openOnInit",
            "trapFocus",
            "focusTrapOptions"
        ]);
        const classPrefixToUse = classPrefixFromProps || classPrefixFromContext;
        const slug = slugFromArg || slugFromProp;
        const isOpen = modalState[slug] && modalState[slug].isOpen;
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                if (trapFocus) {
                    const currentModal = modalRef.current;
                    if (trapHasBeenLayed.current === false && currentModal) {
                        const newTrap = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$focus$2d$trap$2f$dist$2f$focus$2d$trap$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createFocusTrap"])(currentModal, Object.assign(Object.assign({}, focusTrapOptions), {
                            fallbackFocus: (focusTrapOptions === null || focusTrapOptions === void 0 ? void 0 : focusTrapOptions.fallbackFocus) || currentModal,
                            allowOutsideClick: typeof focusTrapOptions.allowOutsideClick !== 'undefined' ? focusTrapOptions.allowOutsideClick : true
                        }));
                        setTrap(newTrap);
                        trapHasBeenLayed.current = true;
                    }
                }
            }
        }["asModal.ModalWrap.useEffect"], [
            trapFocus,
            layTrap,
            focusTrapOptions
        ]);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                setLayTrap(true);
            }
        }["asModal.ModalWrap.useEffect"], []);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                if (trap) {
                    if (isOpen) trap.activate();
                    else trap.deactivate();
                }
                return ({
                    "asModal.ModalWrap.useEffect": ()=>{
                        if (trap) trap.deactivate();
                    }
                })["asModal.ModalWrap.useEffect"];
            }
        }["asModal.ModalWrap.useEffect"], [
            isOpen,
            trap
        ]);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                if (isOpen) setCloseOnBlur(closeOnBlur);
            }
        }["asModal.ModalWrap.useEffect"], [
            isOpen,
            closeOnBlur,
            setCloseOnBlur
        ]);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                const currentModal = modalRef.current;
                if (currentModal) {
                    if (isOpen && lockBodyScroll) {
                        setBodyScrollLock(true, currentModal);
                    } else {
                        setBodyScrollLock(false, currentModal);
                    }
                }
                return ({
                    "asModal.ModalWrap.useEffect": ()=>{
                        if (currentModal) {
                            setBodyScrollLock(false, currentModal);
                        }
                    }
                })["asModal.ModalWrap.useEffect"];
            }
        }["asModal.ModalWrap.useEffect"], [
            isOpen,
            lockBodyScroll,
            setBodyScrollLock
        ]);
        const [timedOpen, setTimedOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(isOpen);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                if (!isOpen) setTimeout({
                    "asModal.ModalWrap.useEffect": ()=>setTimedOpen(false)
                }["asModal.ModalWrap.useEffect"], transTime);
                else setTimedOpen(isOpen);
            }
        }["asModal.ModalWrap.useEffect"], [
            isOpen,
            transTime
        ]);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
            "asModal.ModalWrap.useEffect": ()=>{
                if (openOnInit) {
                    openModal(slug);
                }
            }
        }["asModal.ModalWrap.useEffect"], [
            slug,
            openOnInit,
            openModal
        ]);
        if (containerRef.current) {
            const baseClass = classPrefixToUse ? `${classPrefixToUse}__${itemBaseClass}` : itemBaseClass;
            const mergedClasses = [
                baseClass,
                `${baseClass}--slug-${slug}`,
                className
            ].filter(Boolean).join(' ');
            const mergedAttributes = Object.assign({
                role: Tag !== 'dialog' ? 'dialog' : undefined,
                open: Tag === 'dialog' ? timedOpen || isOpen : undefined,
                'aria-modal': true,
                'aria-label': !rest['aria-labelledby'] ? slug : undefined
            }, rest);
            return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createPortal((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$CSSTransition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__CSSTransition$3e$__["CSSTransition"], {
                nodeRef: modalRef,
                timeout: transTime,
                in: isOpen,
                classNames: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$ModalProvider$2f$generateTransitionClasses$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["generateTransitionClasses"])(baseClass),
                appear: true,
                onEnter,
                onEntering,
                onEntered,
                onExit,
                onExiting,
                onExited,
                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Tag, Object.assign({
                    ref: modalRef,
                    id: (rest === null || rest === void 0 ? void 0 : rest.id) || slug,
                    className: mergedClasses
                }, mergedAttributes, {
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(ModalComponent, Object.assign({}, props, {
                        isOpen,
                        modal
                    }))
                }))
            }), containerRef.current);
        }
        return null;
    };
    return ModalWrap;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/useModal/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useModal",
    ()=>useModal
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$ModalProvider$2f$context$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@faceless-ui/modal/dist/ModalProvider/context.js [app-client] (ecmascript)");
'use client';
;
;
const useModal = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$faceless$2d$ui$2f$modal$2f$dist$2f$ModalProvider$2f$context$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["ModalContext"]);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/core/dist/floating-ui.core.mjs [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "arrow",
    ()=>arrow,
    "autoPlacement",
    ()=>autoPlacement,
    "computePosition",
    ()=>computePosition,
    "detectOverflow",
    ()=>detectOverflow,
    "flip",
    ()=>flip,
    "hide",
    ()=>hide,
    "inline",
    ()=>inline,
    "limitShift",
    ()=>limitShift,
    "offset",
    ()=>offset,
    "shift",
    ()=>shift,
    "size",
    ()=>size
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs [app-client] (ecmascript)");
;
;
function computeCoordsFromPlacement(_ref, placement, rtl) {
    let { reference, floating } = _ref;
    const sideAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement);
    const alignmentAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignmentAxis"])(placement);
    const alignLength = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAxisLength"])(alignmentAxis);
    const side = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement);
    const isVertical = sideAxis === 'y';
    const commonX = reference.x + reference.width / 2 - floating.width / 2;
    const commonY = reference.y + reference.height / 2 - floating.height / 2;
    const commonAlign = reference[alignLength] / 2 - floating[alignLength] / 2;
    let coords;
    switch(side){
        case 'top':
            coords = {
                x: commonX,
                y: reference.y - floating.height
            };
            break;
        case 'bottom':
            coords = {
                x: commonX,
                y: reference.y + reference.height
            };
            break;
        case 'right':
            coords = {
                x: reference.x + reference.width,
                y: commonY
            };
            break;
        case 'left':
            coords = {
                x: reference.x - floating.width,
                y: commonY
            };
            break;
        default:
            coords = {
                x: reference.x,
                y: reference.y
            };
    }
    const alignment = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement);
    if (alignment) {
        coords[alignmentAxis] += commonAlign * (alignment === 'end' ? 1 : -1) * (rtl && isVertical ? -1 : 1);
    }
    return coords;
}
/**
 * Resolves with an object of overflow side offsets that determine how much the
 * element is overflowing a given clipping boundary on each side.
 * - positive = overflowing the boundary by that number of pixels
 * - negative = how many pixels left before it will overflow
 * - 0 = lies flush with the boundary
 * @see https://floating-ui.com/docs/detectOverflow
 */ async function detectOverflow(state, options) {
    var _await$platform$isEle;
    if (options === void 0) {
        options = {};
    }
    const { x, y, platform, rects, elements, strategy } = state;
    const { boundary = 'clippingAncestors', rootBoundary = 'viewport', elementContext = 'floating', altBoundary = false, padding = 0 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
    const paddingObject = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPaddingObject"])(padding);
    const altContext = elementContext === 'floating' ? 'reference' : 'floating';
    const element = elements[altBoundary ? altContext : elementContext];
    const clippingClientRect = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])(await platform.getClippingRect({
        element: ((_await$platform$isEle = await (platform.isElement == null ? void 0 : platform.isElement(element))) != null ? _await$platform$isEle : true) ? element : element.contextElement || await (platform.getDocumentElement == null ? void 0 : platform.getDocumentElement(elements.floating)),
        boundary,
        rootBoundary,
        strategy
    }));
    const rect = elementContext === 'floating' ? {
        x,
        y,
        width: rects.floating.width,
        height: rects.floating.height
    } : rects.reference;
    const offsetParent = await (platform.getOffsetParent == null ? void 0 : platform.getOffsetParent(elements.floating));
    const offsetScale = await (platform.isElement == null ? void 0 : platform.isElement(offsetParent)) && await (platform.getScale == null ? void 0 : platform.getScale(offsetParent)) || {
        x: 1,
        y: 1
    };
    const elementClientRect = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])(platform.convertOffsetParentRelativeRectToViewportRelativeRect ? await platform.convertOffsetParentRelativeRectToViewportRelativeRect({
        elements,
        rect,
        offsetParent,
        strategy
    }) : rect);
    return {
        top: (clippingClientRect.top - elementClientRect.top + paddingObject.top) / offsetScale.y,
        bottom: (elementClientRect.bottom - clippingClientRect.bottom + paddingObject.bottom) / offsetScale.y,
        left: (clippingClientRect.left - elementClientRect.left + paddingObject.left) / offsetScale.x,
        right: (elementClientRect.right - clippingClientRect.right + paddingObject.right) / offsetScale.x
    };
}
// Maximum number of resets that can occur before bailing to avoid infinite reset loops.
const MAX_RESET_COUNT = 50;
/**
 * Computes the `x` and `y` coordinates that will place the floating element
 * next to a given reference element.
 *
 * This export does not have any `platform` interface logic. You will need to
 * write one for the platform you are using Floating UI with.
 */ const computePosition = async (reference, floating, config)=>{
    const { placement = 'bottom', strategy = 'absolute', middleware = [], platform } = config;
    const platformWithDetectOverflow = platform.detectOverflow ? platform : {
        ...platform,
        detectOverflow
    };
    const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(floating));
    let rects = await platform.getElementRects({
        reference,
        floating,
        strategy
    });
    let { x, y } = computeCoordsFromPlacement(rects, placement, rtl);
    let statefulPlacement = placement;
    let resetCount = 0;
    const middlewareData = {};
    for(let i = 0; i < middleware.length; i++){
        const currentMiddleware = middleware[i];
        if (!currentMiddleware) {
            continue;
        }
        const { name, fn } = currentMiddleware;
        const { x: nextX, y: nextY, data, reset } = await fn({
            x,
            y,
            initialPlacement: placement,
            placement: statefulPlacement,
            strategy,
            middlewareData,
            rects,
            platform: platformWithDetectOverflow,
            elements: {
                reference,
                floating
            }
        });
        x = nextX != null ? nextX : x;
        y = nextY != null ? nextY : y;
        middlewareData[name] = {
            ...middlewareData[name],
            ...data
        };
        if (reset && resetCount < MAX_RESET_COUNT) {
            resetCount++;
            if (typeof reset === 'object') {
                if (reset.placement) {
                    statefulPlacement = reset.placement;
                }
                if (reset.rects) {
                    rects = reset.rects === true ? await platform.getElementRects({
                        reference,
                        floating,
                        strategy
                    }) : reset.rects;
                }
                ({ x, y } = computeCoordsFromPlacement(rects, statefulPlacement, rtl));
            }
            i = -1;
        }
    }
    return {
        x,
        y,
        placement: statefulPlacement,
        strategy,
        middlewareData
    };
};
/**
 * Provides data to position an inner element of the floating element so that it
 * appears centered to the reference element.
 * @see https://floating-ui.com/docs/arrow
 */ const arrow = (options)=>({
        name: 'arrow',
        options,
        async fn (state) {
            const { x, y, placement, rects, platform, elements, middlewareData } = state;
            // Since `element` is required, we don't Partial<> the type.
            const { element, padding = 0 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state) || {};
            if (element == null) {
                return {};
            }
            const paddingObject = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPaddingObject"])(padding);
            const coords = {
                x,
                y
            };
            const axis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignmentAxis"])(placement);
            const length = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAxisLength"])(axis);
            const arrowDimensions = await platform.getDimensions(element);
            const isYAxis = axis === 'y';
            const minProp = isYAxis ? 'top' : 'left';
            const maxProp = isYAxis ? 'bottom' : 'right';
            const clientProp = isYAxis ? 'clientHeight' : 'clientWidth';
            const endDiff = rects.reference[length] + rects.reference[axis] - coords[axis] - rects.floating[length];
            const startDiff = coords[axis] - rects.reference[axis];
            const arrowOffsetParent = await (platform.getOffsetParent == null ? void 0 : platform.getOffsetParent(element));
            let clientSize = arrowOffsetParent ? arrowOffsetParent[clientProp] : 0;
            // DOM platform can return `window` as the `offsetParent`.
            if (!clientSize || !await (platform.isElement == null ? void 0 : platform.isElement(arrowOffsetParent))) {
                clientSize = elements.floating[clientProp] || rects.floating[length];
            }
            const centerToReference = endDiff / 2 - startDiff / 2;
            // If the padding is large enough that it causes the arrow to no longer be
            // centered, modify the padding so that it is centered.
            const largestPossiblePadding = clientSize / 2 - arrowDimensions[length] / 2 - 1;
            const minPadding = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(paddingObject[minProp], largestPossiblePadding);
            const maxPadding = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(paddingObject[maxProp], largestPossiblePadding);
            // Make sure the arrow doesn't overflow the floating element if the center
            // point is outside the floating element's bounds.
            const max = clientSize - arrowDimensions[length] - maxPadding;
            const center = clientSize / 2 - arrowDimensions[length] / 2 + centerToReference;
            const offset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["clamp"])(minPadding, center, max);
            // If the reference is small enough that the arrow's padding causes it to
            // to point to nothing for an aligned placement, adjust the offset of the
            // floating element itself. To ensure `shift()` continues to take action,
            // a single reset is performed when this is true.
            const shouldAddOffset = !middlewareData.arrow && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement) != null && center !== offset && rects.reference[length] / 2 - (center < minPadding ? minPadding : maxPadding) - arrowDimensions[length] / 2 < 0;
            const alignmentOffset = shouldAddOffset ? center < minPadding ? center - minPadding : center - max : 0;
            return {
                [axis]: coords[axis] + alignmentOffset,
                data: {
                    [axis]: offset,
                    centerOffset: center - offset - alignmentOffset,
                    ...shouldAddOffset && {
                        alignmentOffset
                    }
                },
                reset: shouldAddOffset
            };
        }
    });
function getPlacementList(alignment, autoAlignment, allowedPlacements) {
    const allowedPlacementsSortedByAlignment = alignment ? [
        ...allowedPlacements.filter((placement)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement) === alignment),
        ...allowedPlacements.filter((placement)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement) !== alignment)
    ] : allowedPlacements.filter((placement)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement) === placement);
    return allowedPlacementsSortedByAlignment.filter((placement)=>{
        if (alignment) {
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement) === alignment || (autoAlignment ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOppositeAlignmentPlacement"])(placement) !== placement : false);
        }
        return true;
    });
}
/**
 * Optimizes the visibility of the floating element by choosing the placement
 * that has the most space available automatically, without needing to specify a
 * preferred placement. Alternative to `flip`.
 * @see https://floating-ui.com/docs/autoPlacement
 */ const autoPlacement = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'autoPlacement',
        options,
        async fn (state) {
            var _middlewareData$autoP, _middlewareData$autoP2, _placementsThatFitOnE;
            const { rects, middlewareData, placement, platform, elements } = state;
            const { crossAxis = false, alignment, allowedPlacements = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["placements"], autoAlignment = true, ...detectOverflowOptions } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            const placements$1 = alignment !== undefined || allowedPlacements === __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["placements"] ? getPlacementList(alignment || null, autoAlignment, allowedPlacements) : allowedPlacements;
            const currentIndex = ((_middlewareData$autoP = middlewareData.autoPlacement) == null ? void 0 : _middlewareData$autoP.index) || 0;
            const currentPlacement = placements$1[currentIndex];
            if (currentPlacement == null) {
                return {};
            }
            // Make `computeCoords` start from the right place.
            if (placement !== currentPlacement) {
                return {
                    reset: {
                        placement: placements$1[0]
                    }
                };
            }
            const overflow = await platform.detectOverflow(state, detectOverflowOptions);
            const alignmentSides = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignmentSides"])(currentPlacement, rects, await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating)));
            const currentOverflows = [
                overflow[(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(currentPlacement)],
                overflow[alignmentSides[0]],
                overflow[alignmentSides[1]]
            ];
            const allOverflows = [
                ...((_middlewareData$autoP2 = middlewareData.autoPlacement) == null ? void 0 : _middlewareData$autoP2.overflows) || [],
                {
                    placement: currentPlacement,
                    overflows: currentOverflows
                }
            ];
            const nextPlacement = placements$1[currentIndex + 1];
            // There are more placements to check.
            if (nextPlacement) {
                return {
                    data: {
                        index: currentIndex + 1,
                        overflows: allOverflows
                    },
                    reset: {
                        placement: nextPlacement
                    }
                };
            }
            const placementsSortedByMostSpace = allOverflows.map((d)=>{
                const alignment = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(d.placement);
                return [
                    d.placement,
                    alignment && crossAxis ? // Check along the mainAxis and main crossAxis side.
                    d.overflows.slice(0, 2).reduce((acc, v)=>acc + v, 0) : // Check only the mainAxis.
                    d.overflows[0],
                    d.overflows
                ];
            }).sort((a, b)=>a[1] - b[1]);
            const placementsThatFitOnEachSide = placementsSortedByMostSpace.filter((d)=>d[2].slice(0, // Aligned placements should not check their opposite crossAxis
                // side.
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(d[0]) ? 2 : 3).every((v)=>v <= 0));
            const resetPlacement = ((_placementsThatFitOnE = placementsThatFitOnEachSide[0]) == null ? void 0 : _placementsThatFitOnE[0]) || placementsSortedByMostSpace[0][0];
            if (resetPlacement !== placement) {
                return {
                    data: {
                        index: currentIndex + 1,
                        overflows: allOverflows
                    },
                    reset: {
                        placement: resetPlacement
                    }
                };
            }
            return {};
        }
    };
};
/**
 * Optimizes the visibility of the floating element by flipping the `placement`
 * in order to keep it in view when the preferred placement(s) will overflow the
 * clipping boundary. Alternative to `autoPlacement`.
 * @see https://floating-ui.com/docs/flip
 */ const flip = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'flip',
        options,
        async fn (state) {
            var _middlewareData$arrow, _middlewareData$flip;
            const { placement, middlewareData, rects, initialPlacement, platform, elements } = state;
            const { mainAxis: checkMainAxis = true, crossAxis: checkCrossAxis = true, fallbackPlacements: specifiedFallbackPlacements, fallbackStrategy = 'bestFit', fallbackAxisSideDirection = 'none', flipAlignment = true, ...detectOverflowOptions } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            // If a reset by the arrow was caused due to an alignment offset being
            // added, we should skip any logic now since `flip()` has already done its
            // work.
            // https://github.com/floating-ui/floating-ui/issues/2549#issuecomment-1719601643
            if ((_middlewareData$arrow = middlewareData.arrow) != null && _middlewareData$arrow.alignmentOffset) {
                return {};
            }
            const side = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement);
            const initialSideAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(initialPlacement);
            const isBasePlacement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(initialPlacement) === initialPlacement;
            const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating));
            const fallbackPlacements = specifiedFallbackPlacements || (isBasePlacement || !flipAlignment ? [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOppositePlacement"])(initialPlacement)
            ] : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getExpandedPlacements"])(initialPlacement));
            const hasFallbackAxisSideDirection = fallbackAxisSideDirection !== 'none';
            if (!specifiedFallbackPlacements && hasFallbackAxisSideDirection) {
                fallbackPlacements.push(...(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOppositeAxisPlacements"])(initialPlacement, flipAlignment, fallbackAxisSideDirection, rtl));
            }
            const placements = [
                initialPlacement,
                ...fallbackPlacements
            ];
            const overflow = await platform.detectOverflow(state, detectOverflowOptions);
            const overflows = [];
            let overflowsData = ((_middlewareData$flip = middlewareData.flip) == null ? void 0 : _middlewareData$flip.overflows) || [];
            if (checkMainAxis) {
                overflows.push(overflow[side]);
            }
            if (checkCrossAxis) {
                const sides = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignmentSides"])(placement, rects, rtl);
                overflows.push(overflow[sides[0]], overflow[sides[1]]);
            }
            overflowsData = [
                ...overflowsData,
                {
                    placement,
                    overflows
                }
            ];
            // One or more sides is overflowing.
            if (!overflows.every((side)=>side <= 0)) {
                var _middlewareData$flip2, _overflowsData$filter;
                const nextIndex = (((_middlewareData$flip2 = middlewareData.flip) == null ? void 0 : _middlewareData$flip2.index) || 0) + 1;
                const nextPlacement = placements[nextIndex];
                if (nextPlacement) {
                    const ignoreCrossAxisOverflow = checkCrossAxis === 'alignment' ? initialSideAxis !== (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(nextPlacement) : false;
                    if (!ignoreCrossAxisOverflow || // We leave the current main axis only if every placement on that axis
                    // overflows the main axis.
                    overflowsData.every((d)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(d.placement) === initialSideAxis ? d.overflows[0] > 0 : true)) {
                        // Try next placement and re-run the lifecycle.
                        return {
                            data: {
                                index: nextIndex,
                                overflows: overflowsData
                            },
                            reset: {
                                placement: nextPlacement
                            }
                        };
                    }
                }
                // First, find the candidates that fit on the mainAxis side of overflow,
                // then find the placement that fits the best on the main crossAxis side.
                let resetPlacement = (_overflowsData$filter = overflowsData.filter((d)=>d.overflows[0] <= 0).sort((a, b)=>a.overflows[1] - b.overflows[1])[0]) == null ? void 0 : _overflowsData$filter.placement;
                // Otherwise fallback.
                if (!resetPlacement) {
                    switch(fallbackStrategy){
                        case 'bestFit':
                            {
                                var _overflowsData$filter2;
                                const placement = (_overflowsData$filter2 = overflowsData.filter((d)=>{
                                    if (hasFallbackAxisSideDirection) {
                                        const currentSideAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(d.placement);
                                        return currentSideAxis === initialSideAxis || // Create a bias to the `y` side axis due to horizontal
                                        // reading directions favoring greater width.
                                        currentSideAxis === 'y';
                                    }
                                    return true;
                                }).map((d)=>[
                                        d.placement,
                                        d.overflows.filter((overflow)=>overflow > 0).reduce((acc, overflow)=>acc + overflow, 0)
                                    ]).sort((a, b)=>a[1] - b[1])[0]) == null ? void 0 : _overflowsData$filter2[0];
                                if (placement) {
                                    resetPlacement = placement;
                                }
                                break;
                            }
                        case 'initialPlacement':
                            resetPlacement = initialPlacement;
                            break;
                    }
                }
                if (placement !== resetPlacement) {
                    return {
                        reset: {
                            placement: resetPlacement
                        }
                    };
                }
            }
            return {};
        }
    };
};
function getSideOffsets(overflow, rect) {
    return {
        top: overflow.top - rect.height,
        right: overflow.right - rect.width,
        bottom: overflow.bottom - rect.height,
        left: overflow.left - rect.width
    };
}
function isAnySideFullyClipped(overflow) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["sides"].some((side)=>overflow[side] >= 0);
}
/**
 * Provides data to hide the floating element in applicable situations, such as
 * when it is not in the same clipping context as the reference element.
 * @see https://floating-ui.com/docs/hide
 */ const hide = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'hide',
        options,
        async fn (state) {
            const { rects, platform } = state;
            const { strategy = 'referenceHidden', ...detectOverflowOptions } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            switch(strategy){
                case 'referenceHidden':
                    {
                        const overflow = await platform.detectOverflow(state, {
                            ...detectOverflowOptions,
                            elementContext: 'reference'
                        });
                        const offsets = getSideOffsets(overflow, rects.reference);
                        return {
                            data: {
                                referenceHiddenOffsets: offsets,
                                referenceHidden: isAnySideFullyClipped(offsets)
                            }
                        };
                    }
                case 'escaped':
                    {
                        const overflow = await platform.detectOverflow(state, {
                            ...detectOverflowOptions,
                            altBoundary: true
                        });
                        const offsets = getSideOffsets(overflow, rects.floating);
                        return {
                            data: {
                                escapedOffsets: offsets,
                                escaped: isAnySideFullyClipped(offsets)
                            }
                        };
                    }
                default:
                    {
                        return {};
                    }
            }
        }
    };
};
function getBoundingRect(rects) {
    const minX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(...rects.map((rect)=>rect.left));
    const minY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(...rects.map((rect)=>rect.top));
    const maxX = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(...rects.map((rect)=>rect.right));
    const maxY = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(...rects.map((rect)=>rect.bottom));
    return {
        x: minX,
        y: minY,
        width: maxX - minX,
        height: maxY - minY
    };
}
function getRectsByLine(rects) {
    const sortedRects = rects.slice().sort((a, b)=>a.y - b.y);
    const groups = [];
    let prevRect = null;
    for(let i = 0; i < sortedRects.length; i++){
        const rect = sortedRects[i];
        if (!prevRect || rect.y - prevRect.y > prevRect.height / 2) {
            groups.push([
                rect
            ]);
        } else {
            groups[groups.length - 1].push(rect);
        }
        prevRect = rect;
    }
    return groups.map((rect)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])(getBoundingRect(rect)));
}
/**
 * Provides improved positioning for inline reference elements that can span
 * over multiple lines, such as hyperlinks or range selections.
 * @see https://floating-ui.com/docs/inline
 */ const inline = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'inline',
        options,
        async fn (state) {
            const { placement, elements, rects, platform, strategy } = state;
            // A MouseEvent's client{X,Y} coords can be up to 2 pixels off a
            // ClientRect's bounds, despite the event listener being triggered. A
            // padding of 2 seems to handle this issue.
            const { padding = 2, x, y } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            const nativeClientRects = Array.from(await (platform.getClientRects == null ? void 0 : platform.getClientRects(elements.reference)) || []);
            // No rects (e.g. a hidden or detached reference, or a collapsed range) —
            // keep the existing reference rect rather than resetting to an invalid
            // one with non-finite values.
            if (!nativeClientRects.length) {
                return {};
            }
            const clientRects = getRectsByLine(nativeClientRects);
            const fallback = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])(getBoundingRect(nativeClientRects));
            const paddingObject = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getPaddingObject"])(padding);
            function getBoundingClientRect() {
                // There are two rects and they are disjoined.
                if (clientRects.length === 2 && (clientRects[0].left > clientRects[1].right || clientRects[1].left > clientRects[0].right) && x != null && y != null) {
                    // Find the first rect in which the point is fully inside.
                    return clientRects.find((rect)=>x > rect.left - paddingObject.left && x < rect.right + paddingObject.right && y > rect.top - paddingObject.top && y < rect.bottom + paddingObject.bottom) || fallback;
                }
                // There are 2 or more connected rects.
                if (clientRects.length >= 2) {
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement) === 'y') {
                        const firstRect = clientRects[0];
                        const lastRect = clientRects[clientRects.length - 1];
                        const isTop = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement) === 'top';
                        const top = firstRect.top;
                        const bottom = lastRect.bottom;
                        const left = isTop ? firstRect.left : lastRect.left;
                        const right = isTop ? firstRect.right : lastRect.right;
                        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])({
                            x: left,
                            y: top,
                            width: right - left,
                            height: bottom - top
                        });
                    }
                    const isLeftSide = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement) === 'left';
                    const maxRight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(...clientRects.map((rect)=>rect.right));
                    const minLeft = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(...clientRects.map((rect)=>rect.left));
                    const measureRects = clientRects.filter((rect)=>isLeftSide ? rect.left === minLeft : rect.right === maxRight);
                    const top = measureRects[0].top;
                    const bottom = measureRects[measureRects.length - 1].bottom;
                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])({
                        x: minLeft,
                        y: top,
                        width: maxRight - minLeft,
                        height: bottom - top
                    });
                }
                return fallback;
            }
            const resetRects = await platform.getElementRects({
                reference: {
                    getBoundingClientRect
                },
                floating: elements.floating,
                strategy
            });
            if (rects.reference.x !== resetRects.reference.x || rects.reference.y !== resetRects.reference.y || rects.reference.width !== resetRects.reference.width || rects.reference.height !== resetRects.reference.height) {
                return {
                    reset: {
                        rects: resetRects
                    }
                };
            }
            return {};
        }
    };
};
const originSides = /*#__PURE__*/ new Set([
    'left',
    'top'
]);
// For type backwards-compatibility, the `OffsetOptions` type was also
// Derivable.
async function convertValueToCoords(state, options) {
    const { placement, platform, elements } = state;
    const rtl = await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating));
    const side = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement);
    const alignment = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement);
    const isVertical = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement) === 'y';
    const mainAxisMulti = originSides.has(side) ? -1 : 1;
    const crossAxisMulti = rtl && isVertical ? -1 : 1;
    const rawValue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
    // eslint-disable-next-line prefer-const
    let { mainAxis, crossAxis, alignmentAxis } = typeof rawValue === 'number' ? {
        mainAxis: rawValue,
        crossAxis: 0,
        alignmentAxis: null
    } : {
        mainAxis: rawValue.mainAxis || 0,
        crossAxis: rawValue.crossAxis || 0,
        alignmentAxis: rawValue.alignmentAxis
    };
    if (alignment && typeof alignmentAxis === 'number') {
        crossAxis = alignment === 'end' ? alignmentAxis * -1 : alignmentAxis;
    }
    return isVertical ? {
        x: crossAxis * crossAxisMulti,
        y: mainAxis * mainAxisMulti
    } : {
        x: mainAxis * mainAxisMulti,
        y: crossAxis * crossAxisMulti
    };
}
/**
 * Modifies the placement by translating the floating element along the
 * specified axes.
 * A number (shorthand for `mainAxis` or distance), or an axes configuration
 * object may be passed.
 * @see https://floating-ui.com/docs/offset
 */ const offset = function(options) {
    if (options === void 0) {
        options = 0;
    }
    return {
        name: 'offset',
        options,
        async fn (state) {
            var _middlewareData$offse, _middlewareData$arrow;
            const { x, y, placement, middlewareData } = state;
            const diffCoords = await convertValueToCoords(state, options);
            // If the placement is the same and the arrow caused an alignment offset
            // then we don't need to change the positioning coordinates.
            if (placement === ((_middlewareData$offse = middlewareData.offset) == null ? void 0 : _middlewareData$offse.placement) && (_middlewareData$arrow = middlewareData.arrow) != null && _middlewareData$arrow.alignmentOffset) {
                return {};
            }
            return {
                x: x + diffCoords.x,
                y: y + diffCoords.y,
                data: {
                    ...diffCoords,
                    placement
                }
            };
        }
    };
};
/**
 * Optimizes the visibility of the floating element by shifting it in order to
 * keep it in view when it will overflow the clipping boundary.
 * @see https://floating-ui.com/docs/shift
 */ const shift = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'shift',
        options,
        async fn (state) {
            const { x, y, placement, platform } = state;
            const { mainAxis: checkMainAxis = true, crossAxis: checkCrossAxis = false, limiter = {
                fn: (_ref)=>{
                    let { x, y } = _ref;
                    return {
                        x,
                        y
                    };
                }
            }, ...detectOverflowOptions } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            const coords = {
                x,
                y
            };
            const overflow = await platform.detectOverflow(state, detectOverflowOptions);
            const crossAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement);
            const mainAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOppositeAxis"])(crossAxis);
            let mainAxisCoord = coords[mainAxis];
            let crossAxisCoord = coords[crossAxis];
            const clampCoord = (axis, coord)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["clamp"])(coord + overflow[axis === 'y' ? 'top' : 'left'], coord, coord - overflow[axis === 'y' ? 'bottom' : 'right']);
            if (checkMainAxis) {
                mainAxisCoord = clampCoord(mainAxis, mainAxisCoord);
            }
            if (checkCrossAxis) {
                crossAxisCoord = clampCoord(crossAxis, crossAxisCoord);
            }
            const limitedCoords = limiter.fn({
                ...state,
                [mainAxis]: mainAxisCoord,
                [crossAxis]: crossAxisCoord
            });
            return {
                ...limitedCoords,
                data: {
                    x: limitedCoords.x - x,
                    y: limitedCoords.y - y,
                    enabled: {
                        [mainAxis]: checkMainAxis,
                        [crossAxis]: checkCrossAxis
                    }
                }
            };
        }
    };
};
/**
 * Built-in `limiter` that will stop `shift()` at a certain point.
 */ const limitShift = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        options,
        fn (state) {
            var _rawOffset$mainAxis, _rawOffset$crossAxis;
            const { x, y, placement, rects, middlewareData } = state;
            const { offset = 0, mainAxis: checkMainAxis = true, crossAxis: checkCrossAxis = true } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            const coords = {
                x,
                y
            };
            const crossAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement);
            const mainAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOppositeAxis"])(crossAxis);
            let mainAxisCoord = coords[mainAxis];
            let crossAxisCoord = coords[crossAxis];
            const rawOffset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(offset, state);
            const computedOffset = typeof rawOffset === 'number' ? {
                mainAxis: rawOffset,
                crossAxis: 0
            } : {
                mainAxis: (_rawOffset$mainAxis = rawOffset.mainAxis) != null ? _rawOffset$mainAxis : 0,
                crossAxis: (_rawOffset$crossAxis = rawOffset.crossAxis) != null ? _rawOffset$crossAxis : 0
            };
            if (checkMainAxis) {
                const len = mainAxis === 'y' ? 'height' : 'width';
                const limitMin = rects.reference[mainAxis] - rects.floating[len] + computedOffset.mainAxis;
                const limitMax = rects.reference[mainAxis] + rects.reference[len] - computedOffset.mainAxis;
                if (mainAxisCoord < limitMin) {
                    mainAxisCoord = limitMin;
                } else if (mainAxisCoord > limitMax) {
                    mainAxisCoord = limitMax;
                }
            }
            if (checkCrossAxis) {
                var _middlewareData$offse, _middlewareData$offse2;
                const len = mainAxis === 'y' ? 'width' : 'height';
                const isOriginSide = originSides.has((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement));
                const limitMin = rects.reference[crossAxis] - rects.floating[len] + (isOriginSide ? ((_middlewareData$offse = middlewareData.offset) == null ? void 0 : _middlewareData$offse[crossAxis]) || 0 : 0) + (isOriginSide ? 0 : computedOffset.crossAxis);
                const limitMax = rects.reference[crossAxis] + rects.reference[len] + (isOriginSide ? 0 : ((_middlewareData$offse2 = middlewareData.offset) == null ? void 0 : _middlewareData$offse2[crossAxis]) || 0) - (isOriginSide ? computedOffset.crossAxis : 0);
                if (crossAxisCoord < limitMin) {
                    crossAxisCoord = limitMin;
                } else if (crossAxisCoord > limitMax) {
                    crossAxisCoord = limitMax;
                }
            }
            return {
                [mainAxis]: mainAxisCoord,
                [crossAxis]: crossAxisCoord
            };
        }
    };
};
// Method syntax keeps callback parameters bivariant, but expressing the
// explicit `| undefined` required by `exactOptionalPropertyTypes` needs
// property syntax, which is contravariant under `strictFunctionTypes`.
// Extracting the function from a method position restores that bivariance so
// consumers can still assign callbacks with narrower parameter types.
/**
 * Provides data that allows you to change the size of the floating element —
 * for instance, prevent it from overflowing the clipping boundary or match the
 * width of the reference element.
 * @see https://floating-ui.com/docs/size
 */ const size = function(options) {
    if (options === void 0) {
        options = {};
    }
    return {
        name: 'size',
        options,
        async fn (state) {
            const { placement, rects, platform, elements } = state;
            const { apply = ()=>{}, ...detectOverflowOptions } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["evaluate"])(options, state);
            const overflow = await platform.detectOverflow(state, detectOverflowOptions);
            const side = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSide"])(placement);
            const alignment = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getAlignment"])(placement);
            const isYAxis = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSideAxis"])(placement) === 'y';
            const { width, height } = rects.floating;
            let heightSide;
            let widthSide;
            if (side === 'top' || side === 'bottom') {
                heightSide = side;
                widthSide = alignment === (await (platform.isRTL == null ? void 0 : platform.isRTL(elements.floating)) ? 'start' : 'end') ? 'left' : 'right';
            } else {
                widthSide = side;
                heightSide = alignment === 'end' ? 'top' : 'bottom';
            }
            const maximumClippingHeight = height - overflow.top - overflow.bottom;
            const maximumClippingWidth = width - overflow.left - overflow.right;
            const overflowAvailableHeight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(height - overflow[heightSide], maximumClippingHeight);
            const overflowAvailableWidth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(width - overflow[widthSide], maximumClippingWidth);
            const shiftData = state.middlewareData.shift;
            const noShift = !shiftData;
            let availableHeight = overflowAvailableHeight;
            let availableWidth = overflowAvailableWidth;
            if (shiftData != null && shiftData.enabled.x) {
                availableWidth = maximumClippingWidth;
            }
            if (shiftData != null && shiftData.enabled.y) {
                availableHeight = maximumClippingHeight;
            }
            if (noShift && !alignment) {
                if (isYAxis) {
                    availableWidth = width - 2 * (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(overflow.left, overflow.right);
                } else {
                    availableHeight = height - 2 * (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(overflow.top, overflow.bottom);
                }
            }
            await apply({
                ...state,
                availableWidth,
                availableHeight
            });
            const nextDimensions = await platform.getDimensions(elements.floating);
            if (width !== nextDimensions.width || height !== nextDimensions.height) {
                return {
                    reset: {
                        rects: true
                    }
                };
            }
            return {};
        }
    };
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "arrow",
    ()=>arrow,
    "autoPlacement",
    ()=>autoPlacement,
    "autoUpdate",
    ()=>autoUpdate,
    "computePosition",
    ()=>computePosition,
    "detectOverflow",
    ()=>detectOverflow,
    "flip",
    ()=>flip,
    "hide",
    ()=>hide,
    "inline",
    ()=>inline,
    "limitShift",
    ()=>limitShift,
    "offset",
    ()=>offset,
    "platform",
    ()=>platform,
    "shift",
    ()=>shift,
    "size",
    ()=>size
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/core/dist/floating-ui.core.mjs [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/utils/dist/floating-ui.utils.dom.mjs [app-client] (ecmascript)");
;
;
;
;
function getCssDimensions(element) {
    const css = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(element);
    // In testing environments, the `width` and `height` properties are empty
    // strings for SVG elements, returning NaN. Fallback to `0` in this case.
    let width = parseFloat(css.width) || 0;
    let height = parseFloat(css.height) || 0;
    const hasOffset = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(element);
    const offsetWidth = hasOffset ? element.offsetWidth : width;
    const offsetHeight = hasOffset ? element.offsetHeight : height;
    const shouldFallback = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["round"])(width) !== offsetWidth || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["round"])(height) !== offsetHeight;
    if (shouldFallback) {
        width = offsetWidth;
        height = offsetHeight;
    }
    return {
        width,
        height,
        $: shouldFallback
    };
}
function unwrapElement(element) {
    return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(element) ? element.contextElement : element;
}
function getScale(element) {
    const domElement = unwrapElement(element);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(domElement)) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(1);
    }
    const rect = domElement.getBoundingClientRect();
    const { width, height, $ } = getCssDimensions(domElement);
    let x = ($ ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["round"])(rect.width) : rect.width) / width;
    let y = ($ ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["round"])(rect.height) : rect.height) / height;
    // 0, NaN, or Infinity should always fallback to 1.
    if (!x || !Number.isFinite(x)) {
        x = 1;
    }
    if (!y || !Number.isFinite(y)) {
        y = 1;
    }
    return {
        x,
        y
    };
}
const noOffsets = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
function getVisualOffsets(element) {
    const win = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(element);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isWebKit"])() || !win.visualViewport) {
        return noOffsets;
    }
    return {
        x: win.visualViewport.offsetLeft,
        y: win.visualViewport.offsetTop
    };
}
function shouldAddVisualOffsets(element, isFixed, floatingOffsetParent) {
    if (isFixed === void 0) {
        isFixed = false;
    }
    return !!floatingOffsetParent && isFixed && floatingOffsetParent === (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(element);
}
function getBoundingClientRect(element, includeScale, isFixedStrategy, offsetParent) {
    if (includeScale === void 0) {
        includeScale = false;
    }
    if (isFixedStrategy === void 0) {
        isFixedStrategy = false;
    }
    const clientRect = element.getBoundingClientRect();
    const domElement = unwrapElement(element);
    let scale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(1);
    if (includeScale) {
        if (offsetParent) {
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(offsetParent)) {
                scale = getScale(offsetParent);
            }
        } else {
            scale = getScale(element);
        }
    }
    const visualOffsets = shouldAddVisualOffsets(domElement, isFixedStrategy, offsetParent) ? getVisualOffsets(domElement) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
    let x = (clientRect.left + visualOffsets.x) / scale.x;
    let y = (clientRect.top + visualOffsets.y) / scale.y;
    let width = clientRect.width / scale.x;
    let height = clientRect.height / scale.y;
    if (domElement && offsetParent) {
        const win = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(domElement);
        const offsetWin = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(offsetParent) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(offsetParent) : offsetParent;
        let currentWin = win;
        let currentIFrame = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getFrameElement"])(currentWin);
        while(currentIFrame && offsetWin !== currentWin){
            const iframeScale = getScale(currentIFrame);
            const iframeRect = currentIFrame.getBoundingClientRect();
            const css = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(currentIFrame);
            const left = iframeRect.left + (currentIFrame.clientLeft + parseFloat(css.paddingLeft)) * iframeScale.x;
            const top = iframeRect.top + (currentIFrame.clientTop + parseFloat(css.paddingTop)) * iframeScale.y;
            x *= iframeScale.x;
            y *= iframeScale.y;
            width *= iframeScale.x;
            height *= iframeScale.y;
            x += left;
            y += top;
            currentWin = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(currentIFrame);
            currentIFrame = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getFrameElement"])(currentWin);
        }
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])({
        width,
        height,
        x,
        y
    });
}
// If <html> has a CSS width greater than the viewport, then this will be
// incorrect for RTL.
function getWindowScrollBarX(element, rect) {
    const leftScroll = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeScroll"])(element).scrollLeft;
    if (!rect) {
        return getBoundingClientRect((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(element)).left + leftScroll;
    }
    return rect.left + leftScroll;
}
function getHTMLOffset(documentElement, scroll) {
    const htmlRect = documentElement.getBoundingClientRect();
    const x = htmlRect.left + scroll.scrollLeft - getWindowScrollBarX(documentElement, htmlRect);
    const y = htmlRect.top + scroll.scrollTop;
    return {
        x,
        y
    };
}
function convertOffsetParentRelativeRectToViewportRelativeRect(_ref) {
    let { elements, rect, offsetParent, strategy } = _ref;
    const isFixed = strategy === 'fixed';
    const documentElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(offsetParent);
    const topLayer = elements ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTopLayer"])(elements.floating) : false;
    if (offsetParent === documentElement || topLayer && isFixed) {
        return rect;
    }
    let scroll = {
        scrollLeft: 0,
        scrollTop: 0
    };
    let scale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(1);
    const offsets = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
    const isOffsetParentAnElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(offsetParent);
    if (isOffsetParentAnElement || !isFixed) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeName"])(offsetParent) !== 'body' || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isOverflowElement"])(documentElement)) {
            scroll = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeScroll"])(offsetParent);
        }
        if (isOffsetParentAnElement) {
            const offsetRect = getBoundingClientRect(offsetParent);
            scale = getScale(offsetParent);
            offsets.x = offsetRect.x + offsetParent.clientLeft;
            offsets.y = offsetRect.y + offsetParent.clientTop;
        }
    }
    const htmlOffset = documentElement && !isOffsetParentAnElement && !isFixed ? getHTMLOffset(documentElement, scroll) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
    return {
        width: rect.width * scale.x,
        height: rect.height * scale.y,
        x: rect.x * scale.x - scroll.scrollLeft * scale.x + offsets.x + htmlOffset.x,
        y: rect.y * scale.y - scroll.scrollTop * scale.y + offsets.y + htmlOffset.y
    };
}
function getClientRects(element) {
    return element.getClientRects ? Array.from(element.getClientRects()) : [];
}
// Gets the entire size of the scrollable document area, even extending outside
// of the `<html>` and `<body>` rect bounds if horizontally scrollable.
function getDocumentRect(html) {
    const scroll = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeScroll"])(html);
    const body = html.ownerDocument.body;
    const width = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(html.scrollWidth, html.clientWidth, body.scrollWidth, body.clientWidth);
    const height = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(html.scrollHeight, html.clientHeight, body.scrollHeight, body.clientHeight);
    let x = -scroll.scrollLeft + getWindowScrollBarX(html);
    const y = -scroll.scrollTop;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(body).direction === 'rtl') {
        x += (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(html.clientWidth, body.clientWidth) - width;
    }
    return {
        width,
        height,
        x,
        y
    };
}
// Safety check: ensure the scrollbar space is reasonable in case this
// calculation is affected by unusual styles.
// Most scrollbars leave 15-18px of space.
const SCROLLBAR_MAX = 25;
function getViewportRect(element, strategy, rootBoundary) {
    if (rootBoundary === void 0) {
        rootBoundary = 'viewport';
    }
    const isLayoutViewport = rootBoundary === 'layoutViewport';
    const win = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(element);
    const html = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(element);
    const visualViewport = win.visualViewport;
    let width = html.clientWidth;
    let height = html.clientHeight;
    let x = 0;
    let y = 0;
    if (visualViewport) {
        // Client coordinates are relative to the layout viewport, except in
        // WebKit with an `absolute` strategy, where they are relative to the
        // visual viewport.
        const layoutRelativeClientCoords = !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isWebKit"])() || strategy === 'fixed';
        if (isLayoutViewport) {
            if (!layoutRelativeClientCoords) {
                x = -visualViewport.offsetLeft;
                y = -visualViewport.offsetTop;
            }
        } else {
            width = visualViewport.width;
            height = visualViewport.height;
            if (layoutRelativeClientCoords) {
                x = visualViewport.offsetLeft;
                y = visualViewport.offsetTop;
            }
        }
    }
    const windowScrollbarX = getWindowScrollBarX(html);
    // `scrollbar-gutter: stable` on the <html> reserves gutter space that shrinks
    // the visual width but isn't reflected in `html.clientWidth`, so subtract it.
    // Only the inline-end (right) gutter can hold the scrollbar; `both-edges` also
    // reserves an empty inline-start gutter that clips nothing, so exclude just
    // the one scrollbar-side gutter — halve the measured (two-gutter) total. A
    // left-side scrollbar (`windowScrollbarX > 0`) is already handled by
    // `getHTMLOffset`/`visualViewport.width`; skip it here.
    if (windowScrollbarX <= 0) {
        const doc = html.ownerDocument;
        const body = doc.body;
        const bodyStyles = getComputedStyle(body);
        const bodyMarginInline = doc.compatMode === 'CSS1Compat' ? parseFloat(bodyStyles.marginLeft) + parseFloat(bodyStyles.marginRight) || 0 : 0;
        const reservedWidth = Math.abs(html.clientWidth - body.clientWidth - bodyMarginInline);
        const gutter = getComputedStyle(html).scrollbarGutter === 'stable both-edges' ? reservedWidth / 2 : reservedWidth;
        if (gutter <= SCROLLBAR_MAX) {
            width -= gutter;
        }
    }
    return {
        width,
        height,
        x,
        y
    };
}
// Returns the inner client rect, subtracting scrollbars if present.
function getInnerBoundingClientRect(element, strategy) {
    const clientRect = getBoundingClientRect(element, true, strategy === 'fixed');
    const top = clientRect.top + element.clientTop;
    const left = clientRect.left + element.clientLeft;
    const scale = getScale(element);
    const width = element.clientWidth * scale.x;
    const height = element.clientHeight * scale.y;
    const x = left * scale.x;
    const y = top * scale.y;
    return {
        width,
        height,
        x,
        y
    };
}
function getClientRectFromClippingAncestor(element, clippingAncestor, strategy) {
    let rect;
    if (clippingAncestor === 'viewport' || clippingAncestor === 'layoutViewport') {
        rect = getViewportRect(element, strategy, clippingAncestor);
    } else if (clippingAncestor === 'document') {
        rect = getDocumentRect((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(element));
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(clippingAncestor)) {
        rect = getInnerBoundingClientRect(clippingAncestor, strategy);
    } else {
        const visualOffsets = getVisualOffsets(element);
        rect = {
            x: clippingAncestor.x - visualOffsets.x,
            y: clippingAncestor.y - visualOffsets.y,
            width: clippingAncestor.width,
            height: clippingAncestor.height
        };
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["rectToClientRect"])(rect);
}
// A "clipping ancestor" is an `overflow` element with the characteristic of
// clipping (or hiding) child elements. This returns all clipping ancestors
// of the given element up the tree.
function getClippingElementAncestors(element, cache) {
    const cachedResult = cache.get(element);
    if (cachedResult) {
        return cachedResult;
    }
    let result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOverflowAncestors"])(element, [], false).filter((el)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(el) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeName"])(el) !== 'body');
    let lastKeptComputedStyle = null;
    const elementIsFixed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(element).position === 'fixed';
    let currentNode = elementIsFixed ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getParentNode"])(element) : element;
    // https://developer.mozilla.org/en-US/docs/Web/CSS/Containing_block#identifying_the_containing_block
    while((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(currentNode) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isLastTraversableNode"])(currentNode)){
        const computedStyle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(currentNode);
        const currentNodeIsContaining = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isContainingBlock"])(currentNode);
        // Position of the containing block chain below the current node. A fixed
        // element whose containing block hasn't been found yet is a fixed chain.
        const lastPosition = lastKeptComputedStyle ? lastKeptComputedStyle.position : elementIsFixed ? 'fixed' : '';
        // A non-containing ancestor does not clip the element when the chain
        // below it escapes it: a fixed chain escapes all ancestors up to the
        // next containing block, an absolute chain escapes static ancestors.
        const shouldDropCurrentNode = !currentNodeIsContaining && (lastPosition === 'fixed' || lastPosition === 'absolute' && computedStyle.position === 'static');
        if (shouldDropCurrentNode) {
            // Drop non-containing blocks.
            result = result.filter((ancestor)=>ancestor !== currentNode);
        } else {
            // The kept node carries the chain position for the next iteration.
            lastKeptComputedStyle = computedStyle;
        }
        currentNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getParentNode"])(currentNode);
    }
    cache.set(element, result);
    return result;
}
// Gets the maximum area that the element is visible in due to any number of
// clipping ancestors.
function getClippingRect(_ref) {
    let { element, boundary, rootBoundary, strategy } = _ref;
    const elementClippingAncestors = boundary === 'clippingAncestors' ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTopLayer"])(element) ? [] : getClippingElementAncestors(element, this._c) : [].concat(boundary);
    const clippingAncestors = [
        ...elementClippingAncestors,
        rootBoundary
    ];
    const firstRect = getClientRectFromClippingAncestor(element, clippingAncestors[0], strategy);
    let top = firstRect.top;
    let right = firstRect.right;
    let bottom = firstRect.bottom;
    let left = firstRect.left;
    for(let i = 1; i < clippingAncestors.length; i++){
        const rect = getClientRectFromClippingAncestor(element, clippingAncestors[i], strategy);
        top = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(rect.top, top);
        right = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(rect.right, right);
        bottom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(rect.bottom, bottom);
        left = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(rect.left, left);
    }
    return {
        width: right - left,
        height: bottom - top,
        x: left,
        y: top
    };
}
function getDimensions(element) {
    const { width, height } = getCssDimensions(element);
    return {
        width,
        height
    };
}
function getRectRelativeToOffsetParent(element, offsetParent, strategy) {
    const isOffsetParentAnElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(offsetParent);
    const documentElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(offsetParent);
    const isFixed = strategy === 'fixed';
    const rect = getBoundingClientRect(element, true, isFixed, offsetParent);
    let scroll = {
        scrollLeft: 0,
        scrollTop: 0
    };
    const offsets = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
    if (isOffsetParentAnElement || !isFixed) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeName"])(offsetParent) !== 'body' || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isOverflowElement"])(documentElement)) {
            scroll = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getNodeScroll"])(offsetParent);
        }
        if (isOffsetParentAnElement) {
            const offsetRect = getBoundingClientRect(offsetParent, true, isFixed, offsetParent);
            offsets.x = offsetRect.x + offsetParent.clientLeft;
            offsets.y = offsetRect.y + offsetParent.clientTop;
        }
    }
    // If the <body> scrollbar appears on the left (e.g. RTL systems). Use
    // Firefox with layout.scrollbar.side = 3 in about:config to test this.
    if (!isOffsetParentAnElement && documentElement) {
        offsets.x = getWindowScrollBarX(documentElement);
    }
    const htmlOffset = documentElement && !isOffsetParentAnElement && !isFixed ? getHTMLOffset(documentElement, scroll) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createCoords"])(0);
    const x = rect.left + scroll.scrollLeft - offsets.x - htmlOffset.x;
    const y = rect.top + scroll.scrollTop - offsets.y - htmlOffset.y;
    return {
        x,
        y,
        width: rect.width,
        height: rect.height
    };
}
function isStaticPositioned(element) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(element).position === 'static';
}
function getTrueOffsetParent(element, polyfill) {
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(element) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(element).position === 'fixed') {
        return null;
    }
    if (polyfill) {
        return polyfill(element);
    }
    let rawOffsetParent = element.offsetParent;
    // Firefox returns the <html> element as the offsetParent if it's non-static,
    // while Chrome and Safari return the <body> element. The <body> element must
    // be used to perform the correct calculations even if the <html> element is
    // non-static.
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(element) === rawOffsetParent) {
        rawOffsetParent = rawOffsetParent.ownerDocument.body;
    }
    return rawOffsetParent;
}
// Gets the closest ancestor positioned element. Handles some edge cases,
// such as table ancestors and cross browser bugs.
function getOffsetParent(element, polyfill) {
    const win = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(element);
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTopLayer"])(element)) {
        return win;
    }
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isHTMLElement"])(element)) {
        let svgOffsetParent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getParentNode"])(element);
        while(svgOffsetParent && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isLastTraversableNode"])(svgOffsetParent)){
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"])(svgOffsetParent) && !isStaticPositioned(svgOffsetParent)) {
                return svgOffsetParent;
            }
            svgOffsetParent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getParentNode"])(svgOffsetParent);
        }
        return win;
    }
    let offsetParent = getTrueOffsetParent(element, polyfill);
    while(offsetParent && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTableElement"])(offsetParent) && isStaticPositioned(offsetParent)){
        offsetParent = getTrueOffsetParent(offsetParent, polyfill);
    }
    if (offsetParent && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isLastTraversableNode"])(offsetParent) && isStaticPositioned(offsetParent) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isContainingBlock"])(offsetParent)) {
        return win;
    }
    return offsetParent || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getContainingBlock"])(element) || win;
}
const getElementRects = async function(data) {
    const getOffsetParentFn = this.getOffsetParent || getOffsetParent;
    const getDimensionsFn = this.getDimensions;
    const floatingDimensions = await getDimensionsFn(data.floating);
    return {
        reference: getRectRelativeToOffsetParent(data.reference, await getOffsetParentFn(data.floating), data.strategy),
        floating: {
            x: 0,
            y: 0,
            width: floatingDimensions.width,
            height: floatingDimensions.height
        }
    };
};
function isRTL(element) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getComputedStyle"])(element).direction === 'rtl';
}
const platform = {
    convertOffsetParentRelativeRectToViewportRelativeRect,
    getDocumentElement: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"],
    getClippingRect,
    getOffsetParent,
    getElementRects,
    getClientRects,
    getDimensions,
    getScale,
    isElement: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isElement"],
    isRTL
};
function rectsAreEqual(a, b) {
    return a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;
}
// https://samthor.au/2021/observing-dom/
function observeMove(element, onMove, ancestorResize) {
    let io = null;
    let timeoutId;
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getDocumentElement"])(element);
    function cleanup() {
        var _io;
        clearTimeout(timeoutId);
        (_io = io) == null || _io.disconnect();
        io = null;
    }
    function refresh(skip, threshold) {
        if (skip === void 0) {
            skip = false;
        }
        if (threshold === void 0) {
            threshold = 1;
        }
        cleanup();
        const elementRectForRootMargin = element.getBoundingClientRect();
        const { left, top, width, height } = elementRectForRootMargin;
        if (!skip) {
            onMove();
        }
        if (!width || !height) {
            return;
        }
        const insetTop = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["floor"])(top);
        const insetRight = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["floor"])(root.clientWidth - (left + width));
        const insetBottom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["floor"])(root.clientHeight - (top + height));
        const insetLeft = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["floor"])(left);
        const rootMargin = -insetTop + "px " + -insetRight + "px " + -insetBottom + "px " + -insetLeft + "px";
        const options = {
            rootMargin,
            threshold: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["max"])(0, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["min"])(1, threshold)) || 1
        };
        let isFirstUpdate = true;
        function handleObserve(entries) {
            const ratio = entries[0].intersectionRatio;
            // The entry is a snapshot, so the reference may have moved since the
            // intersection was computed (under performance constraints, or between
            // consecutive frames of a multi-frame layout shift). The reported ratio
            // and the observed area are stale in that case and cannot be trusted to
            // detect subsequent movement, so refresh regardless of the ratio.
            if (!rectsAreEqual(elementRectForRootMargin, element.getBoundingClientRect())) {
                return refresh();
            }
            if (ratio !== threshold) {
                if (!isFirstUpdate) {
                    return refresh();
                }
                if (!ratio) {
                    // If the reference is clipped in place, the ratio is 0. Throttle
                    // the refresh to prevent an infinite loop of updates.
                    timeoutId = setTimeout(()=>{
                        refresh(false, 1e-7);
                    }, 1000);
                } else {
                    refresh(false, ratio);
                }
            }
            isFirstUpdate = false;
        }
        // Older browsers don't support a `document` as the root and will throw an
        // error.
        try {
            io = new IntersectionObserver(handleObserve, {
                ...options,
                // Handle <iframe>s
                root: root.ownerDocument
            });
        } catch (_e) {
            io = new IntersectionObserver(handleObserve, options);
        }
        io.observe(element);
    }
    const win = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getWindow"])(element);
    // The window is a resize ancestor, so when `ancestorResize` is enabled its
    // listener already runs the update on resize. Here we only need to rebuild
    // the `IntersectionObserver` for the new root size, skipping a redundant
    // update. When `ancestorResize` is disabled, this becomes the sole update.
    const handleResize = ()=>refresh(ancestorResize);
    win.addEventListener('resize', handleResize);
    refresh(true);
    return ()=>{
        win.removeEventListener('resize', handleResize);
        cleanup();
    };
}
/**
 * Automatically updates the position of the floating element when necessary.
 * Should only be called when the floating element is mounted on the DOM or
 * visible on the screen.
 * @returns cleanup function that should be invoked when the floating element is
 * removed from the DOM or hidden from the screen.
 * @see https://floating-ui.com/docs/autoUpdate
 */ function autoUpdate(reference, floating, update, options) {
    if (options === void 0) {
        options = {};
    }
    const { ancestorScroll = true, ancestorResize = true, elementResize = typeof ResizeObserver === 'function', layoutShift = typeof IntersectionObserver === 'function', animationFrame = false } = options;
    const referenceEl = unwrapElement(reference);
    const ancestors = ancestorScroll || ancestorResize ? [
        ...referenceEl ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOverflowAncestors"])(referenceEl) : [],
        ...floating ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$utils$2f$dist$2f$floating$2d$ui$2e$utils$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getOverflowAncestors"])(floating) : []
    ] : [];
    ancestors.forEach((ancestor)=>{
        ancestorScroll && ancestor.addEventListener('scroll', update);
        ancestorResize && ancestor.addEventListener('resize', update);
    });
    const cleanupIo = referenceEl && layoutShift ? observeMove(referenceEl, update, ancestorResize) : null;
    let reobserveFrame = -1;
    let resizeObserver = null;
    if (elementResize) {
        resizeObserver = new ResizeObserver((_ref)=>{
            let [firstEntry] = _ref;
            if (firstEntry && firstEntry.target === referenceEl && resizeObserver && floating) {
                // Prevent update loops when using the `size` middleware.
                // https://github.com/floating-ui/floating-ui/issues/1740
                resizeObserver.unobserve(floating);
                cancelAnimationFrame(reobserveFrame);
                reobserveFrame = requestAnimationFrame(()=>{
                    var _resizeObserver;
                    (_resizeObserver = resizeObserver) == null || _resizeObserver.observe(floating);
                });
            }
            update();
        });
        if (referenceEl && !animationFrame) {
            resizeObserver.observe(referenceEl);
        }
        if (floating) {
            resizeObserver.observe(floating);
        }
    }
    let frameId;
    let prevRefRect = animationFrame ? getBoundingClientRect(reference) : null;
    if (animationFrame) {
        frameLoop();
    }
    function frameLoop() {
        const nextRefRect = getBoundingClientRect(reference);
        if (prevRefRect && !rectsAreEqual(prevRefRect, nextRefRect)) {
            update();
        }
        prevRefRect = nextRefRect;
        frameId = requestAnimationFrame(frameLoop);
    }
    update();
    return ()=>{
        var _resizeObserver2;
        ancestors.forEach((ancestor)=>{
            ancestorScroll && ancestor.removeEventListener('scroll', update);
            ancestorResize && ancestor.removeEventListener('resize', update);
        });
        cleanupIo == null || cleanupIo();
        (_resizeObserver2 = resizeObserver) == null || _resizeObserver2.disconnect();
        resizeObserver = null;
        if (animationFrame) {
            cancelAnimationFrame(frameId);
        }
    };
}
/**
 * Resolves with an object of overflow side offsets that determine how much the
 * element is overflowing a given clipping boundary on each side.
 * - positive = overflowing the boundary by that number of pixels
 * - negative = how many pixels left before it will overflow
 * - 0 = lies flush with the boundary
 * @see https://floating-ui.com/docs/detectOverflow
 */ const detectOverflow = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["detectOverflow"];
/**
 * Modifies the placement by translating the floating element along the
 * specified axes.
 * A number (shorthand for `mainAxis` or distance), or an axes configuration
 * object may be passed.
 * @see https://floating-ui.com/docs/offset
 */ const offset = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["offset"];
/**
 * Optimizes the visibility of the floating element by choosing the placement
 * that has the most space available automatically, without needing to specify a
 * preferred placement. Alternative to `flip`.
 * @see https://floating-ui.com/docs/autoPlacement
 */ const autoPlacement = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["autoPlacement"];
/**
 * Optimizes the visibility of the floating element by shifting it in order to
 * keep it in view when it will overflow the clipping boundary.
 * @see https://floating-ui.com/docs/shift
 */ const shift = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["shift"];
/**
 * Optimizes the visibility of the floating element by flipping the `placement`
 * in order to keep it in view when the preferred placement(s) will overflow the
 * clipping boundary. Alternative to `autoPlacement`.
 * @see https://floating-ui.com/docs/flip
 */ const flip = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["flip"];
/**
 * Provides data that allows you to change the size of the floating element —
 * for instance, prevent it from overflowing the clipping boundary or match the
 * width of the reference element.
 * @see https://floating-ui.com/docs/size
 */ const size = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["size"];
/**
 * Provides data to hide the floating element in applicable situations, such as
 * when it is not in the same clipping context as the reference element.
 * @see https://floating-ui.com/docs/hide
 */ const hide = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["hide"];
/**
 * Provides data to position an inner element of the floating element so that it
 * appears centered to the reference element.
 * @see https://floating-ui.com/docs/arrow
 */ const arrow = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["arrow"];
/**
 * Provides improved positioning for inline reference elements that can span
 * over multiple lines, such as hyperlinks or range selections.
 * @see https://floating-ui.com/docs/inline
 */ const inline = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["inline"];
/**
 * Built-in `limiter` that will stop `shift()` at a certain point.
 */ const limitShift = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["limitShift"];
/**
 * Computes the `x` and `y` coordinates that will place the floating element
 * next to a given reference element.
 */ const computePosition = (reference, floating, options)=>{
    // This caches the expensive `getClippingElementAncestors` function so that
    // multiple lifecycle resets re-use the same result. It only lives for a
    // single call. If other functions become expensive, we can add them as well.
    const cache = new Map();
    const mergedOptions = options != null ? options : {};
    const platformWithCache = {
        ...platform,
        ...mergedOptions.platform,
        _c: cache
    };
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$core$2f$dist$2f$floating$2d$ui$2e$core$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["computePosition"])(reference, floating, {
        ...mergedOptions,
        platform: platformWithCache
    });
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/react-dom/dist/floating-ui.react-dom.mjs [app-client] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "arrow",
    ()=>arrow,
    "autoPlacement",
    ()=>autoPlacement,
    "flip",
    ()=>flip,
    "hide",
    ()=>hide,
    "inline",
    ()=>inline,
    "limitShift",
    ()=>limitShift,
    "offset",
    ()=>offset,
    "shift",
    ()=>shift,
    "size",
    ()=>size,
    "useFloating",
    ()=>useFloating
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react-dom/index.js [app-client] (ecmascript)");
;
;
;
;
;
var isClient = typeof document !== 'undefined';
var noop = function noop() {};
var index = isClient ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLayoutEffect"] : noop;
// Fork of `fast-deep-equal` that only does the comparisons we need and compares
// functions
function deepEqual(a, b) {
    if (a === b) {
        return true;
    }
    if (typeof a !== typeof b) {
        return false;
    }
    if (typeof a === 'function' && a.toString() === b.toString()) {
        return true;
    }
    let length;
    let i;
    let keys;
    if (a && b && typeof a === 'object') {
        if (Array.isArray(a)) {
            length = a.length;
            if (length !== b.length) return false;
            for(i = length; i-- !== 0;){
                if (!deepEqual(a[i], b[i])) {
                    return false;
                }
            }
            return true;
        }
        keys = Object.keys(a);
        length = keys.length;
        if (length !== Object.keys(b).length) {
            return false;
        }
        for(i = length; i-- !== 0;){
            if (!({}).hasOwnProperty.call(b, keys[i])) {
                return false;
            }
        }
        for(i = length; i-- !== 0;){
            const key = keys[i];
            if (key === '_owner' && a.$$typeof) {
                continue;
            }
            if (!deepEqual(a[key], b[key])) {
                return false;
            }
        }
        return true;
    }
    return a !== a && b !== b;
}
function getDPR(element) {
    if (typeof window === 'undefined') {
        return 1;
    }
    const win = element.ownerDocument.defaultView || window;
    return win.devicePixelRatio || 1;
}
function roundByDPR(element, value) {
    const dpr = getDPR(element);
    return Math.round(value * dpr) / dpr;
}
function useLatestRef(value) {
    const ref = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](value);
    index(()=>{
        ref.current = value;
    });
    return ref;
}
/**
 * Provides data to position a floating element.
 * @see https://floating-ui.com/docs/useFloating
 */ function useFloating(options) {
    if (options === void 0) {
        options = {};
    }
    const { placement = 'bottom', strategy = 'absolute', middleware = [], platform, elements: { reference: externalReference, floating: externalFloating } = {}, transform = true, whileElementsMounted, open } = options;
    const [data, setData] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"]({
        x: 0,
        y: 0,
        strategy,
        placement,
        middlewareData: {},
        isPositioned: false
    });
    const [latestMiddleware, setLatestMiddleware] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](middleware);
    if (!deepEqual(latestMiddleware, middleware)) {
        setLatestMiddleware(middleware);
    }
    const [_reference, _setReference] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const [_floating, _setFloating] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"](null);
    const setReference = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "useFloating.useCallback[setReference]": (node)=>{
            if (node !== referenceRef.current) {
                referenceRef.current = node;
                _setReference(node);
            }
        }
    }["useFloating.useCallback[setReference]"], []);
    const setFloating = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "useFloating.useCallback[setFloating]": (node)=>{
            if (node !== floatingRef.current) {
                floatingRef.current = node;
                _setFloating(node);
            }
        }
    }["useFloating.useCallback[setFloating]"], []);
    const referenceEl = externalReference || _reference;
    const floatingEl = externalFloating || _floating;
    const referenceRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const floatingRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](null);
    const dataRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](data);
    const hasWhileElementsMounted = whileElementsMounted != null;
    const whileElementsMountedRef = useLatestRef(whileElementsMounted);
    const platformRef = useLatestRef(platform);
    const openRef = useLatestRef(open);
    const update = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"]({
        "useFloating.useCallback[update]": ()=>{
            if (!referenceRef.current || !floatingRef.current) {
                return;
            }
            const config = {
                placement,
                strategy,
                middleware: latestMiddleware
            };
            if (platformRef.current) {
                config.platform = platformRef.current;
            }
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["computePosition"])(referenceRef.current, floatingRef.current, config).then({
                "useFloating.useCallback[update]": (data)=>{
                    const fullData = {
                        ...data,
                        // The floating element's position may be recomputed while it's closed
                        // but still mounted (such as when transitioning out). To ensure
                        // `isPositioned` will be `false` initially on the next open, avoid
                        // setting it to `true` when `open === false` (must be specified).
                        isPositioned: openRef.current !== false
                    };
                    if (isMountedRef.current && !deepEqual(dataRef.current, fullData)) {
                        dataRef.current = fullData;
                        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["flushSync"]({
                            "useFloating.useCallback[update]": ()=>{
                                setData(fullData);
                            }
                        }["useFloating.useCallback[update]"]);
                    }
                }
            }["useFloating.useCallback[update]"]);
        }
    }["useFloating.useCallback[update]"], [
        latestMiddleware,
        placement,
        strategy,
        platformRef,
        openRef
    ]);
    index(()=>{
        if (open === false && dataRef.current.isPositioned) {
            dataRef.current.isPositioned = false;
            setData((data)=>({
                    ...data,
                    isPositioned: false
                }));
        }
    }, [
        open
    ]);
    const isMountedRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"](false);
    index(()=>{
        isMountedRef.current = true;
        return ()=>{
            isMountedRef.current = false;
        };
    }, []);
    index(()=>{
        if (referenceEl) referenceRef.current = referenceEl;
        if (floatingEl) floatingRef.current = floatingEl;
        if (referenceEl && floatingEl) {
            if (whileElementsMountedRef.current) {
                return whileElementsMountedRef.current(referenceEl, floatingEl, update);
            }
            update();
        }
    }, [
        referenceEl,
        floatingEl,
        update,
        whileElementsMountedRef,
        hasWhileElementsMounted
    ]);
    const refs = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "useFloating.useMemo[refs]": ()=>({
                reference: referenceRef,
                floating: floatingRef,
                setReference,
                setFloating
            })
    }["useFloating.useMemo[refs]"], [
        setReference,
        setFloating
    ]);
    const elements = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "useFloating.useMemo[elements]": ()=>({
                reference: referenceEl,
                floating: floatingEl
            })
    }["useFloating.useMemo[elements]"], [
        referenceEl,
        floatingEl
    ]);
    const floatingStyles = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "useFloating.useMemo[floatingStyles]": ()=>{
            const initialStyles = {
                position: strategy,
                left: 0,
                top: 0
            };
            if (!elements.floating) {
                return initialStyles;
            }
            const x = roundByDPR(elements.floating, data.x);
            const y = roundByDPR(elements.floating, data.y);
            if (transform) {
                return {
                    ...initialStyles,
                    transform: "translate(" + x + "px, " + y + "px)",
                    ...getDPR(elements.floating) >= 1.5 && {
                        willChange: 'transform'
                    }
                };
            }
            return {
                position: strategy,
                left: x,
                top: y
            };
        }
    }["useFloating.useMemo[floatingStyles]"], [
        strategy,
        transform,
        elements.floating,
        data.x,
        data.y
    ]);
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"]({
        "useFloating.useMemo": ()=>({
                ...data,
                update,
                refs,
                elements,
                floatingStyles
            })
    }["useFloating.useMemo"], [
        data,
        update,
        refs,
        elements,
        floatingStyles
    ]);
}
/**
 * Provides data to position an inner element of the floating element so that it
 * appears centered to the reference element.
 * This wraps the core `arrow` middleware to allow React refs as the element.
 * @see https://floating-ui.com/docs/arrow
 */ const arrow$1 = (options)=>{
    function isRef(value) {
        return ({}).hasOwnProperty.call(value, 'current');
    }
    return {
        name: 'arrow',
        options,
        fn (state) {
            const { element, padding } = typeof options === 'function' ? options(state) : options;
            if (element && isRef(element)) {
                if (element.current != null) {
                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["arrow"])({
                        element: element.current,
                        padding
                    }).fn(state);
                }
                return {};
            }
            if (element) {
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["arrow"])({
                    element,
                    padding
                }).fn(state);
            }
            return {};
        }
    };
};
/**
 * Modifies the placement by translating the floating element along the
 * specified axes.
 * A number (shorthand for `mainAxis` or distance), or an axes configuration
 * object may be passed.
 * @see https://floating-ui.com/docs/offset
 */ const offset = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["offset"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Optimizes the visibility of the floating element by shifting it in order to
 * keep it in view when it will overflow the clipping boundary.
 * @see https://floating-ui.com/docs/shift
 */ const shift = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["shift"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Built-in `limiter` that will stop `shift()` at a certain point.
 */ const limitShift = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["limitShift"])(options);
    return {
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Optimizes the visibility of the floating element by flipping the `placement`
 * in order to keep it in view when the preferred placement(s) will overflow the
 * clipping boundary. Alternative to `autoPlacement`.
 * @see https://floating-ui.com/docs/flip
 */ const flip = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["flip"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Provides data that allows you to change the size of the floating element —
 * for instance, prevent it from overflowing the clipping boundary or match the
 * width of the reference element.
 * @see https://floating-ui.com/docs/size
 */ const size = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["size"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Optimizes the visibility of the floating element by choosing the placement
 * that has the most space available automatically, without needing to specify a
 * preferred placement. Alternative to `flip`.
 * @see https://floating-ui.com/docs/autoPlacement
 */ const autoPlacement = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["autoPlacement"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Provides data to hide the floating element in applicable situations, such as
 * when it is not in the same clipping context as the reference element.
 * @see https://floating-ui.com/docs/hide
 */ const hide = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["hide"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Provides improved positioning for inline reference elements that can span
 * over multiple lines, such as hyperlinks or range selections.
 * @see https://floating-ui.com/docs/inline
 */ const inline = (options, deps)=>{
    const result = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$floating$2d$ui$2f$dom$2f$dist$2f$floating$2d$ui$2e$dom$2e$mjs__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["inline"])(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
/**
 * Provides data to position an inner element of the floating element so that it
 * appears centered to the reference element.
 * This wraps the core `arrow` middleware to allow React refs as the element.
 * @see https://floating-ui.com/docs/arrow
 */ const arrow = (options, deps)=>{
    const result = arrow$1(options);
    return {
        name: result.name,
        fn: result.fn,
        options: [
            options,
            deps
        ]
    };
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/utils/dist/floating-ui.utils.dom.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getComputedStyle",
    ()=>getComputedStyle,
    "getContainingBlock",
    ()=>getContainingBlock,
    "getDocumentElement",
    ()=>getDocumentElement,
    "getFrameElement",
    ()=>getFrameElement,
    "getNearestOverflowAncestor",
    ()=>getNearestOverflowAncestor,
    "getNodeName",
    ()=>getNodeName,
    "getNodeScroll",
    ()=>getNodeScroll,
    "getOverflowAncestors",
    ()=>getOverflowAncestors,
    "getParentNode",
    ()=>getParentNode,
    "getWindow",
    ()=>getWindow,
    "isContainingBlock",
    ()=>isContainingBlock,
    "isElement",
    ()=>isElement,
    "isHTMLElement",
    ()=>isHTMLElement,
    "isLastTraversableNode",
    ()=>isLastTraversableNode,
    "isNode",
    ()=>isNode,
    "isOverflowElement",
    ()=>isOverflowElement,
    "isShadowRoot",
    ()=>isShadowRoot,
    "isTableElement",
    ()=>isTableElement,
    "isTopLayer",
    ()=>isTopLayer,
    "isWebKit",
    ()=>isWebKit
]);
function hasWindow() {
    return typeof window !== 'undefined';
}
function getNodeName(node) {
    if (isNode(node)) {
        return (node.nodeName || '').toLowerCase();
    }
    // Mocked nodes in testing environments may not be instances of Node. By
    // returning `#document` an infinite loop won't occur.
    // https://github.com/floating-ui/floating-ui/issues/2317
    return '#document';
}
function getWindow(node) {
    var _node$ownerDocument;
    return (node == null || (_node$ownerDocument = node.ownerDocument) == null ? void 0 : _node$ownerDocument.defaultView) || window;
}
function getDocumentElement(node) {
    var _ref;
    return (_ref = (isNode(node) ? node.ownerDocument : node.document) || window.document) == null ? void 0 : _ref.documentElement;
}
function isNode(value) {
    if (!hasWindow()) {
        return false;
    }
    return value instanceof Node || value instanceof getWindow(value).Node;
}
function isElement(value) {
    if (!hasWindow()) {
        return false;
    }
    return value instanceof Element || value instanceof getWindow(value).Element;
}
function isHTMLElement(value) {
    if (!hasWindow()) {
        return false;
    }
    return value instanceof HTMLElement || value instanceof getWindow(value).HTMLElement;
}
function isShadowRoot(value) {
    if (!hasWindow() || typeof ShadowRoot === 'undefined') {
        return false;
    }
    return value instanceof ShadowRoot || value instanceof getWindow(value).ShadowRoot;
}
function isOverflowElement(element) {
    const { overflow, overflowX, overflowY, display } = getComputedStyle(element);
    return /auto|scroll|overlay|hidden|clip/.test(overflow + overflowY + overflowX) && display !== 'inline' && display !== 'contents';
}
function isTableElement(element) {
    return /^(table|td|th)$/.test(getNodeName(element));
}
function isTopLayer(element) {
    try {
        if (element.matches(':popover-open')) {
            return true;
        }
    } catch (_e) {
    // no-op
    }
    try {
        return element.matches(':modal');
    } catch (_e) {
        return false;
    }
}
const willChangeRe = /transform|translate|scale|rotate|perspective|filter/;
const containRe = /paint|layout|strict|content/;
const isNotNone = (value)=>!!value && value !== 'none';
let isWebKitValue;
function isContainingBlock(elementOrCss) {
    const css = isElement(elementOrCss) ? getComputedStyle(elementOrCss) : elementOrCss;
    // https://developer.mozilla.org/en-US/docs/Web/CSS/Containing_block#identifying_the_containing_block
    // https://drafts.csswg.org/css-transforms-2/#individual-transforms
    return isNotNone(css.transform) || isNotNone(css.translate) || isNotNone(css.scale) || isNotNone(css.rotate) || isNotNone(css.perspective) || !isWebKit() && (isNotNone(css.backdropFilter) || isNotNone(css.filter)) || willChangeRe.test(css.willChange || '') || containRe.test(css.contain || '');
}
function getContainingBlock(element) {
    let currentNode = getParentNode(element);
    while(isHTMLElement(currentNode) && !isLastTraversableNode(currentNode)){
        if (isContainingBlock(currentNode)) {
            return currentNode;
        } else if (isTopLayer(currentNode)) {
            return null;
        }
        currentNode = getParentNode(currentNode);
    }
    return null;
}
function isWebKit() {
    if (isWebKitValue == null) {
        isWebKitValue = typeof CSS !== 'undefined' && CSS.supports && CSS.supports('-webkit-backdrop-filter', 'none');
    }
    return isWebKitValue;
}
function isLastTraversableNode(node) {
    return /^(html|body|#document)$/.test(getNodeName(node));
}
function getComputedStyle(element) {
    return getWindow(element).getComputedStyle(element);
}
function getNodeScroll(element) {
    if (isElement(element)) {
        return {
            scrollLeft: element.scrollLeft,
            scrollTop: element.scrollTop
        };
    }
    return {
        scrollLeft: element.scrollX,
        scrollTop: element.scrollY
    };
}
function getParentNode(node) {
    if (getNodeName(node) === 'html') {
        return node;
    }
    const result = // Step into the shadow DOM of the parent of a slotted node.
    node.assignedSlot || // DOM Element detected.
    node.parentNode || // ShadowRoot detected.
    isShadowRoot(node) && node.host || // Fallback.
    getDocumentElement(node);
    return isShadowRoot(result) ? result.host : result;
}
function getNearestOverflowAncestor(node) {
    const parentNode = getParentNode(node);
    if (isLastTraversableNode(parentNode)) {
        return (node.ownerDocument || node).body;
    }
    if (isHTMLElement(parentNode) && isOverflowElement(parentNode)) {
        return parentNode;
    }
    return getNearestOverflowAncestor(parentNode);
}
function getOverflowAncestors(node, list, traverseIframes) {
    var _node$ownerDocument2;
    if (list === void 0) {
        list = [];
    }
    if (traverseIframes === void 0) {
        traverseIframes = true;
    }
    const scrollableAncestor = getNearestOverflowAncestor(node);
    const isBody = scrollableAncestor === ((_node$ownerDocument2 = node.ownerDocument) == null ? void 0 : _node$ownerDocument2.body);
    const win = getWindow(scrollableAncestor);
    if (isBody) {
        const frameElement = getFrameElement(win);
        return list.concat(win, win.visualViewport || [], isOverflowElement(scrollableAncestor) ? scrollableAncestor : [], frameElement && traverseIframes ? getOverflowAncestors(frameElement) : []);
    } else {
        return list.concat(scrollableAncestor, getOverflowAncestors(scrollableAncestor, [], traverseIframes));
    }
}
function getFrameElement(win) {
    return win.parent && Object.getPrototypeOf(win.parent) ? win.frameElement : null;
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@floating-ui/utils/dist/floating-ui.utils.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "alignments",
    ()=>alignments,
    "clamp",
    ()=>clamp,
    "createCoords",
    ()=>createCoords,
    "evaluate",
    ()=>evaluate,
    "expandPaddingObject",
    ()=>expandPaddingObject,
    "floor",
    ()=>floor,
    "getAlignment",
    ()=>getAlignment,
    "getAlignmentAxis",
    ()=>getAlignmentAxis,
    "getAlignmentSides",
    ()=>getAlignmentSides,
    "getAxisLength",
    ()=>getAxisLength,
    "getExpandedPlacements",
    ()=>getExpandedPlacements,
    "getOppositeAlignmentPlacement",
    ()=>getOppositeAlignmentPlacement,
    "getOppositeAxis",
    ()=>getOppositeAxis,
    "getOppositeAxisPlacements",
    ()=>getOppositeAxisPlacements,
    "getOppositePlacement",
    ()=>getOppositePlacement,
    "getPaddingObject",
    ()=>getPaddingObject,
    "getSide",
    ()=>getSide,
    "getSideAxis",
    ()=>getSideAxis,
    "max",
    ()=>max,
    "min",
    ()=>min,
    "placements",
    ()=>placements,
    "rectToClientRect",
    ()=>rectToClientRect,
    "round",
    ()=>round,
    "sides",
    ()=>sides
]);
/**
 * Custom positioning reference element.
 * @see https://floating-ui.com/docs/virtual-elements
 */ const sides = [
    'top',
    'right',
    'bottom',
    'left'
];
const alignments = [
    'start',
    'end'
];
const placements = /*#__PURE__*/ sides.reduce((acc, side)=>acc.concat(side, side + "-" + alignments[0], side + "-" + alignments[1]), []);
const min = Math.min;
const max = Math.max;
const round = Math.round;
const floor = Math.floor;
const createCoords = (v)=>({
        x: v,
        y: v
    });
const oppositeSideMap = {
    left: 'right',
    right: 'left',
    bottom: 'top',
    top: 'bottom'
};
function clamp(start, value, end) {
    return max(start, min(value, end));
}
function evaluate(value, param) {
    return typeof value === 'function' ? value(param) : value;
}
function getSide(placement) {
    return placement.split('-')[0];
}
function getAlignment(placement) {
    return placement.split('-')[1];
}
function getOppositeAxis(axis) {
    return axis === 'x' ? 'y' : 'x';
}
function getAxisLength(axis) {
    return axis === 'y' ? 'height' : 'width';
}
function getSideAxis(placement) {
    const firstChar = placement[0];
    return firstChar === 't' || firstChar === 'b' ? 'y' : 'x';
}
function getAlignmentAxis(placement) {
    return getOppositeAxis(getSideAxis(placement));
}
function getAlignmentSides(placement, rects, rtl) {
    if (rtl === void 0) {
        rtl = false;
    }
    const alignment = getAlignment(placement);
    const alignmentAxis = getAlignmentAxis(placement);
    const length = getAxisLength(alignmentAxis);
    let mainAlignmentSide = alignmentAxis === 'x' ? alignment === (rtl ? 'end' : 'start') ? 'right' : 'left' : alignment === 'start' ? 'bottom' : 'top';
    if (rects.reference[length] > rects.floating[length]) {
        mainAlignmentSide = getOppositePlacement(mainAlignmentSide);
    }
    return [
        mainAlignmentSide,
        getOppositePlacement(mainAlignmentSide)
    ];
}
function getExpandedPlacements(placement) {
    const oppositePlacement = getOppositePlacement(placement);
    return [
        getOppositeAlignmentPlacement(placement),
        oppositePlacement,
        getOppositeAlignmentPlacement(oppositePlacement)
    ];
}
function getOppositeAlignmentPlacement(placement) {
    return placement.includes('start') ? placement.replace('start', 'end') : placement.replace('end', 'start');
}
const lrPlacement = [
    'left',
    'right'
];
const rlPlacement = [
    'right',
    'left'
];
const tbPlacement = [
    'top',
    'bottom'
];
const btPlacement = [
    'bottom',
    'top'
];
function getSideList(side, isStart, rtl) {
    switch(side){
        case 'top':
        case 'bottom':
            if (rtl) return isStart ? rlPlacement : lrPlacement;
            return isStart ? lrPlacement : rlPlacement;
        case 'left':
        case 'right':
            return isStart ? tbPlacement : btPlacement;
        default:
            return [];
    }
}
function getOppositeAxisPlacements(placement, flipAlignment, direction, rtl) {
    const alignment = getAlignment(placement);
    let list = getSideList(getSide(placement), direction === 'start', rtl);
    if (alignment) {
        list = list.map((side)=>side + "-" + alignment);
        if (flipAlignment) {
            list = list.concat(list.map(getOppositeAlignmentPlacement));
        }
    }
    return list;
}
function getOppositePlacement(placement) {
    const side = getSide(placement);
    return oppositeSideMap[side] + placement.slice(side.length);
}
function expandPaddingObject(padding) {
    var _padding$top, _padding$right, _padding$bottom, _padding$left;
    return {
        top: (_padding$top = padding.top) != null ? _padding$top : 0,
        right: (_padding$right = padding.right) != null ? _padding$right : 0,
        bottom: (_padding$bottom = padding.bottom) != null ? _padding$bottom : 0,
        left: (_padding$left = padding.left) != null ? _padding$left : 0
    };
}
function getPaddingObject(padding) {
    return typeof padding !== 'number' ? expandPaddingObject(padding) : {
        top: padding,
        right: padding,
        bottom: padding,
        left: padding
    };
}
function rectToClientRect(rect) {
    const { x, y, width, height } = rect;
    return {
        width,
        height,
        top: y,
        left: x,
        right: x + width,
        bottom: y + height,
        x,
        y
    };
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/AssignTenantFieldModal/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AssignTenantFieldModal",
    ()=>AssignTenantFieldModal,
    "AssignTenantFieldTrigger",
    ()=>AssignTenantFieldTrigger,
    "assignTenantModalSlug",
    ()=>assignTenantModalSlug
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Drawer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/elements/Drawer/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.client.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
const assignTenantModalSlug = 'assign-tenant-field-modal';
const baseClass = 'assign-tenant-field-modal';
const AssignTenantFieldTrigger = ()=>{
    const { openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { options } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTenantSelection"])();
    if (options.length <= 1) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PopupList"].Button, {
            onClick: ()=>openModal(assignTenantModalSlug),
            children: t('plugin-multi-tenant:assign-tenant-button-label')
        })
    });
};
const AssignTenantFieldModal = ({ afterModalClose, afterModalOpen, children, onCancel, onConfirm })=>{
    const editDepth = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Drawer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDrawerDepth"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { collectionSlug } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const { getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const collectionConfig = getEntityConfig({
        collectionSlug
    });
    const { closeModal, isModalOpen: isModalOpenFn } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const isModalOpen = isModalOpenFn(assignTenantModalSlug);
    const wasModalOpenRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useRef(isModalOpen);
    const onModalConfirm = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "AssignTenantFieldModal.useCallback[onModalConfirm]": ()=>{
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
            closeModal(assignTenantModalSlug);
        }
    }["AssignTenantFieldModal.useCallback[onModalConfirm]"], [
        onConfirm,
        closeModal
    ]);
    const onModalCancel = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "AssignTenantFieldModal.useCallback[onModalCancel]": ()=>{
            if (typeof onCancel === 'function') {
                onCancel();
            }
            closeModal(assignTenantModalSlug);
        }
    }["AssignTenantFieldModal.useCallback[onModalCancel]"], [
        onCancel,
        closeModal
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "AssignTenantFieldModal.useEffect": ()=>{
            if (wasModalOpenRef.current && !isModalOpen) {
                // modal was open, and now is closed
                if (typeof afterModalClose === 'function') {
                    afterModalClose();
                }
            }
            if (!wasModalOpenRef.current && isModalOpen) {
                // modal was closed, and now is open
                if (typeof afterModalOpen === 'function') {
                    afterModalOpen();
                }
            }
            wasModalOpenRef.current = isModalOpen;
        }
    }["AssignTenantFieldModal.useEffect"], [
        isModalOpen,
        onCancel,
        afterModalClose,
        afterModalOpen
    ]);
    if (!collectionConfig) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Modal"], {
        className: baseClass,
        slug: assignTenantModalSlug,
        style: {
            zIndex: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$elements$2f$Drawer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["drawerZBase"] + editDepth
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                className: `${baseClass}__bg`
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: `${baseClass}__wrapper`,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}__header`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("h3", {
                                children: t('plugin-multi-tenant:assign-tenant-modal-title', {
                                    title
                                })
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
                                className: `${baseClass}__collection-pill`,
                                size: "small",
                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslation"])(collectionConfig.labels.singular, i18n)
                            })
                        ]
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        className: `${baseClass}__content`,
                        children: children
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `${baseClass}__actions`,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                                buttonStyle: "secondary",
                                margin: false,
                                onClick: onModalCancel,
                                children: t('general:cancel')
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                                margin: false,
                                onClick: onModalConfirm,
                                children: t('general:confirm')
                            })
                        ]
                    })
                ]
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/TenantField/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TenantField",
    ()=>TenantField
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.client.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$AssignTenantFieldModal$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/AssignTenantFieldModal/index.client.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const baseClass = 'tenantField';
const TenantField = ({ debug, unique, ...fieldArgs })=>{
    const { entityType, options, selectedTenantID, setEntityType, setTenant } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTenantSelection"])();
    const tenantField = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useField"])();
    const { setValue, showError, value } = tenantField;
    const { isValid: isFormValid } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const { id: docID, collectionSlug } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { isModalOpen, openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const isEditManyModalOpen = collectionSlug ? isModalOpen(`edit-${collectionSlug}`) || isModalOpen(`edit-${collectionSlug}-bulk-uploads`) : false;
    const [modalValue, setModalValue] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(value);
    const localTenantField = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useMemo({
        "TenantField.useMemo[localTenantField]": ()=>({
                ...tenantField,
                initialValue: modalValue,
                setValue: ({
                    "TenantField.useMemo[localTenantField]": (nextValue)=>{
                        setModalValue(nextValue);
                    }
                })["TenantField.useMemo[localTenantField]"],
                value: modalValue
            })
    }["TenantField.useMemo[localTenantField]"], [
        modalValue,
        tenantField
    ]);
    const showField = options.length > 1 && !fieldArgs.field.admin?.hidden && !fieldArgs.field.hidden || debug;
    function getTenantIDToSelect({ selectedTenantID, value }) {
        if (Array.isArray(value)) {
            if (!value.length) {
                return undefined;
            }
            if (!selectedTenantID || !value.includes(selectedTenantID)) {
                return value[0];
            }
            return undefined;
        }
        if (value && selectedTenantID !== value) {
            return value;
        }
        return undefined;
    }
    const syncTenantSelectionFromValue = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantField.useCallback[syncTenantSelectionFromValue]": (tenantValue)=>{
            const tenantID = getTenantIDToSelect({
                selectedTenantID,
                value: tenantValue
            });
            if (tenantID) {
                setTenant({
                    id: tenantID,
                    refresh: false
                });
            }
        }
    }["TenantField.useCallback[syncTenantSelectionFromValue]"], [
        selectedTenantID,
        setTenant
    ]);
    const onConfirm = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantField.useCallback[onConfirm]": ()=>{
            if (hasTenantValueChanged({
                hasMany: fieldArgs.field.hasMany,
                modalValue,
                value
            })) {
                setValue(modalValue);
                syncTenantSelectionFromValue(modalValue);
            }
        }
    }["TenantField.useCallback[onConfirm]"], [
        fieldArgs.field.hasMany,
        modalValue,
        setValue,
        syncTenantSelectionFromValue,
        value
    ]);
    const afterModalOpen = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantField.useCallback[afterModalOpen]": ()=>{
            setModalValue(value);
        }
    }["TenantField.useCallback[afterModalOpen]"], [
        value
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantField.useEffect": ()=>{
            if (!entityType) {
                setEntityType(unique ? 'global' : 'document');
            } else {
                // unique documents are controlled from the global TenantSelector
                if (!unique) {
                    syncTenantSelectionFromValue(value);
                }
            }
            return ({
                "TenantField.useEffect": ()=>{
                    if (entityType) {
                        setEntityType(undefined);
                    }
                }
            })["TenantField.useEffect"];
        }
    }["TenantField.useEffect"], [
        entityType,
        setEntityType,
        syncTenantSelectionFromValue,
        unique,
        value
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantField.useEffect": ()=>{
            if (unique || debug || isEditManyModalOpen) {
                return;
            }
            if (showField && (!isFormValid && showError || !value && !selectedTenantID)) {
                openModal(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$AssignTenantFieldModal$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["assignTenantModalSlug"]);
            }
        }
    }["TenantField.useEffect"], [
        debug,
        isEditManyModalOpen,
        isFormValid,
        showError,
        showField,
        openModal,
        value,
        docID,
        selectedTenantID,
        unique
    ]);
    if (showField) {
        if (debug || isEditManyModalOpen) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TenantRelationshipField, {
                debug: debug,
                fieldArgs: fieldArgs,
                unique: unique
            });
        }
        if (!unique) {
            /** Editing a non-global tenant document */ return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$components$2f$AssignTenantFieldModal$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["AssignTenantFieldModal"], {
                afterModalOpen: afterModalOpen,
                onConfirm: onConfirm,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldPathContext"], {
                    value: tenantField.path,
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldContext"], {
                        value: localTenantField,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(TenantRelationshipField, {
                            fieldArgs: fieldArgs,
                            unique: unique
                        })
                    })
                })
            });
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(SyncFormModified, {});
    }
    return null;
};
const hasTenantValueChanged = ({ hasMany, modalValue, value })=>{
    if (hasMany) {
        const currentValue = value || [];
        const nextValue = modalValue || [];
        return currentValue.length !== nextValue.length || nextValue.some((nextValueItem)=>!currentValue.includes(nextValueItem));
    }
    return value !== modalValue;
};
const TenantRelationshipField = ({ debug, fieldArgs, unique })=>{
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
        className: baseClass,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: `${baseClass}__wrapper`,
            children: [
                debug && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Pill"], {
                    className: `${baseClass}__debug-pill`,
                    pillStyle: "success",
                    size: "small",
                    children: "Multi-Tenant Debug Enabled"
                }),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["RelationshipField"], {
                    ...fieldArgs,
                    field: {
                        ...fieldArgs.field,
                        required: true
                    },
                    readOnly: fieldArgs.readOnly || fieldArgs.field.admin?.readOnly || unique
                })
            ]
        })
    });
};
/**
 * Tells the global selector when the form has been modified
 * so it can display the "Leave without saving" confirmation modal
 * if modified and attempting to change the tenant
 */ const SyncFormModified = ()=>{
    const modified = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useFormModified"])();
    const { setModified } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTenantSelection"])();
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "SyncFormModified.useEffect": ()=>{
            setModified(modified);
        }
    }["SyncFormModified.useEffect"], [
        modified,
        setModified
    ]);
    return null;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/TenantSelector/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TenantSelectorClient",
    ()=>TenantSelectorClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.client.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const confirmLeaveWithoutSavingSlug = 'confirm-leave-without-saving';
const TenantSelectorClient = ({ disabled: disabledFromProps, label, viewType })=>{
    const { entityType, modified, options, selectedTenantID, setTenant } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTenantSelection"])();
    const { closeModal, openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const { i18n, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [tenantSelection, setTenantSelection] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState();
    const switchTenant = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectorClient.useCallback[switchTenant]": (option)=>{
            if (option && 'value' in option) {
                setTenant({
                    id: option.value,
                    refresh: true
                });
            } else {
                setTenant({
                    id: undefined,
                    refresh: true
                });
            }
        }
    }["TenantSelectorClient.useCallback[switchTenant]"], [
        setTenant
    ]);
    const onChange = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectorClient.useCallback[onChange]": (option)=>{
            if (option && 'value' in option && option.value === selectedTenantID) {
                // If the selected option is the same as the current tenant, do nothing
                return;
            }
            if (entityType === 'global' && modified) {
                // If the entityType is 'global' and there are unsaved changes, prompt for confirmation
                setTenantSelection(option);
                openModal(confirmLeaveWithoutSavingSlug);
            } else {
                // If the entityType is not 'document', switch tenant without confirmation
                switchTenant(option);
            }
        }
    }["TenantSelectorClient.useCallback[onChange]"], [
        selectedTenantID,
        entityType,
        modified,
        switchTenant,
        openModal
    ]);
    if (options.length <= 1) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        className: "tenant-selector",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["SelectInput"], {
                isClearable: [
                    'dashboard',
                    'list'
                ].includes(viewType ?? ''),
                label: label ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslation"])(label, i18n) : t('plugin-multi-tenant:nav-tenantSelector-label'),
                name: "setTenant",
                onChange: onChange,
                options: options,
                path: "setTenant",
                readOnly: disabledFromProps || entityType !== 'global' && viewType && [
                    'document',
                    'version'
                ].includes(viewType),
                value: selectedTenantID
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmationModal"], {
                body: t('general:changesNotSaved'),
                cancelLabel: t('general:stayOnThisPage'),
                confirmLabel: t('general:leaveAnyway'),
                heading: t('general:leaveWithoutSaving'),
                modalSlug: confirmLeaveWithoutSavingSlug,
                onCancel: ()=>{
                    closeModal(confirmLeaveWithoutSavingSlug);
                },
                onConfirm: ()=>{
                    switchTenant(tenantSelection);
                }
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/components/WatchTenantCollection/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "WatchTenantCollection",
    ()=>WatchTenantCollection
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.client.js [app-client] (ecmascript)");
'use client';
;
;
;
const WatchTenantCollection = ()=>{
    const { id, collectionSlug } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const operation = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useOperation"])();
    const submitted = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useFormSubmitted"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const { getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const [useAsTitleName] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState({
        "WatchTenantCollection.useState": ()=>getEntityConfig({
                collectionSlug
            }).admin.useAsTitle
    }["WatchTenantCollection.useState"]);
    const titleField = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useFormFields"])({
        "WatchTenantCollection.useFormFields[titleField]": ([fields])=>useAsTitleName ? fields[useAsTitleName] : {}
    }["WatchTenantCollection.useFormFields[titleField]"]);
    const { syncTenants, updateTenants } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$providers$2f$TenantSelectionProvider$2f$index$2e$client$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useTenantSelection"])();
    const syncTenantTitle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useEffectEvent"])({
        "WatchTenantCollection.useEffectEvent[syncTenantTitle]": ()=>{
            if (id) {
                updateTenants({
                    id,
                    label: title
                });
            }
        }
    }["WatchTenantCollection.useEffectEvent[syncTenantTitle]"]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "WatchTenantCollection.useEffect": ()=>{
            // only update the tenant selector when the document saves
            // → aka when initial value changes
            if (id && titleField?.initialValue) {
                void syncTenantTitle();
            }
        }
    }["WatchTenantCollection.useEffect"], [
        id,
        titleField?.initialValue
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "WatchTenantCollection.useEffect": ()=>{
            if (operation === 'create' && submitted) {
                void syncTenants();
            }
        }
    }["WatchTenantCollection.useEffect"], [
        operation,
        submitted,
        syncTenants,
        id
    ]);
    return null;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/providers/TenantSelectionProvider/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "TenantSelectionProviderClient",
    ()=>TenantSelectionProviderClient,
    "useTenantSelection",
    ()=>useTenantSelection
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$utilities$2f$generateCookie$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/utilities/generateCookie.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const Context = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createContext"])({
    entityType: undefined,
    options: [],
    selectedTenantID: undefined,
    setEntityType: ()=>undefined,
    setModified: ()=>undefined,
    setTenant: ()=>null,
    syncTenants: ()=>Promise.resolve(),
    updateTenants: ()=>null
});
const DEFAULT_COOKIE_NAME = 'payload-tenant';
const setTenantCookie = (args)=>{
    const { cookieName = DEFAULT_COOKIE_NAME, value } = args;
    document.cookie = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$utilities$2f$generateCookie$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["generateCookie"])({
        name: cookieName,
        maxAge: 60 * 60 * 24 * 365,
        path: '/',
        returnCookieAsObject: false,
        value: value || ''
    });
};
const deleteTenantCookie = (args = {})=>{
    const { cookieName = DEFAULT_COOKIE_NAME } = args;
    document.cookie = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$multi$2d$tenant$2f$dist$2f$utilities$2f$generateCookie$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["generateCookie"])({
        name: cookieName,
        maxAge: -1,
        path: '/',
        returnCookieAsObject: false,
        value: ''
    });
};
const getTenantCookie = (args = {})=>{
    const { cookieName = DEFAULT_COOKIE_NAME } = args;
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${cookieName}=`);
    if (parts.length === 2) {
        return parts.pop()?.split(';').shift();
    }
    return undefined;
};
const TenantSelectionProviderClient = ({ children, initialTenantOptions, initialValue, tenantsCollectionSlug })=>{
    const [selectedTenantID, setSelectedTenantID] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(initialValue);
    const [modified, setModified] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(false);
    const [entityType, setEntityType] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(undefined);
    const { user } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAuth"])();
    const { config } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const userID = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useMemo({
        "TenantSelectionProviderClient.useMemo[userID]": ()=>user?.id
    }["TenantSelectionProviderClient.useMemo[userID]"], [
        user?.id
    ]);
    const prevUserID = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useRef(userID);
    const userChanged = userID !== prevUserID.current;
    const [tenantOptions, setTenantOptions] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState({
        "TenantSelectionProviderClient.useState": ()=>initialTenantOptions
    }["TenantSelectionProviderClient.useState"]);
    const selectedTenantLabel = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useMemo({
        "TenantSelectionProviderClient.useMemo[selectedTenantLabel]": ()=>tenantOptions.find({
                "TenantSelectionProviderClient.useMemo[selectedTenantLabel]": (option)=>option.value === selectedTenantID
            }["TenantSelectionProviderClient.useMemo[selectedTenantLabel]"])?.label
    }["TenantSelectionProviderClient.useMemo[selectedTenantLabel]"], [
        selectedTenantID,
        tenantOptions
    ]);
    const setTenantAndCookie = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectionProviderClient.useCallback[setTenantAndCookie]": ({ id, refresh })=>{
            setSelectedTenantID(id);
            if (id !== undefined) {
                setTenantCookie({
                    value: String(id)
                });
            } else {
                deleteTenantCookie();
            }
            if (refresh) {
                router.refresh();
            }
        }
    }["TenantSelectionProviderClient.useCallback[setTenantAndCookie]"], [
        router
    ]);
    const setTenant = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectionProviderClient.useCallback[setTenant]": ({ id, refresh })=>{
            if (id === undefined) {
                if (tenantOptions.length > 1 || tenantOptions.length === 0) {
                    // users with multiple tenants can clear the tenant selection
                    setTenantAndCookie({
                        id: undefined,
                        refresh
                    });
                } else if (tenantOptions[0]) {
                    // if there is only one tenant, auto-select that tenant
                    setTenantAndCookie({
                        id: tenantOptions[0].value,
                        refresh: true
                    });
                }
            } else if (!tenantOptions.find({
                "TenantSelectionProviderClient.useCallback[setTenant]": (option)=>option.value === id
            }["TenantSelectionProviderClient.useCallback[setTenant]"])) {
                // if the tenant is invalid, set the first tenant as selected
                setTenantAndCookie({
                    id: tenantOptions[0]?.value,
                    refresh
                });
            } else {
                // if the tenant is in the options, set it as selected
                setTenantAndCookie({
                    id,
                    refresh
                });
            }
        }
    }["TenantSelectionProviderClient.useCallback[setTenant]"], [
        tenantOptions,
        setTenantAndCookie
    ]);
    const syncTenants = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectionProviderClient.useCallback[syncTenants]": async ()=>{
            try {
                const req = await fetch((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                    apiRoute: config.routes.api,
                    path: `/${tenantsCollectionSlug}/populate-tenant-options`
                }), {
                    credentials: 'include',
                    method: 'GET'
                });
                const result = await req.json();
                if (result.tenantOptions && userID) {
                    setTenantOptions(result.tenantOptions);
                    if (result.tenantOptions.length === 1) {
                        setSelectedTenantID(result.tenantOptions[0].value);
                        setTenantCookie({
                            value: String(result.tenantOptions[0].value)
                        });
                    }
                }
            } catch (e) {
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(`Error fetching tenants`);
            }
        }
    }["TenantSelectionProviderClient.useCallback[syncTenants]"], [
        config.routes.api,
        tenantsCollectionSlug,
        userID
    ]);
    const updateTenants = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "TenantSelectionProviderClient.useCallback[updateTenants]": ({ id, label })=>{
            setTenantOptions({
                "TenantSelectionProviderClient.useCallback[updateTenants]": (prev)=>{
                    return prev.map({
                        "TenantSelectionProviderClient.useCallback[updateTenants]": (currentTenant)=>{
                            if (id === currentTenant.value) {
                                return {
                                    label,
                                    value: id
                                };
                            }
                            return currentTenant;
                        }
                    }["TenantSelectionProviderClient.useCallback[updateTenants]"]);
                }
            }["TenantSelectionProviderClient.useCallback[updateTenants]"]);
            void syncTenants();
        }
    }["TenantSelectionProviderClient.useCallback[updateTenants]"], [
        syncTenants
    ]);
    /**
   * Sync server-provided tenant options into client state.
   * When the server component re-renders (e.g., after navigation post-login),
   * it provides updated initialTenantOptions. Since useState() ignores new
   * initial values on re-renders, and re-initializes with stale props on
   * remounts, we sync them explicitly via this effect.
   */ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantSelectionProviderClient.useEffect": ()=>{
            if (initialTenantOptions.length > 0) {
                setTenantOptions({
                    "TenantSelectionProviderClient.useEffect": (prev)=>{
                        if (prev.length === initialTenantOptions.length && prev.every({
                            "TenantSelectionProviderClient.useEffect": (opt, i)=>opt.value === initialTenantOptions[i]?.value
                        }["TenantSelectionProviderClient.useEffect"])) {
                            return prev;
                        }
                        return initialTenantOptions;
                    }
                }["TenantSelectionProviderClient.useEffect"]);
                if (initialTenantOptions.length === 1 && initialTenantOptions[0]) {
                    setSelectedTenantID(initialTenantOptions[0].value);
                    setTenantCookie({
                        value: String(initialTenantOptions[0].value)
                    });
                }
            }
        }
    }["TenantSelectionProviderClient.useEffect"], [
        initialTenantOptions
    ]);
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantSelectionProviderClient.useEffect": ()=>{
            if (userChanged || initialValue && String(initialValue) !== getTenantCookie()) {
                if (userID) {
                    // user logging in
                    void syncTenants();
                } else {
                    // user logging out
                    setSelectedTenantID(undefined);
                    deleteTenantCookie();
                    setTenantOptions({
                        "TenantSelectionProviderClient.useEffect": (prev)=>prev.length > 0 ? [] : prev
                    }["TenantSelectionProviderClient.useEffect"]);
                    router.refresh();
                }
                prevUserID.current = userID;
            }
        }
    }["TenantSelectionProviderClient.useEffect"], [
        userID,
        userChanged,
        syncTenants,
        initialValue,
        router
    ]);
    /**
   * If there is no initial value, clear the tenant and refresh the router.
   * Needed for stale tenantIDs set as a cookie.
   */ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantSelectionProviderClient.useEffect": ()=>{
            if (!initialValue) {
                setTenant({
                    id: undefined,
                    refresh: true
                });
            }
        }
    }["TenantSelectionProviderClient.useEffect"], [
        initialValue,
        setTenant
    ]);
    /**
   * If there is no selected tenant ID and the entity type is 'global', set the first tenant as selected.
   * This ensures that the global tenant is always set when the component mounts.
   */ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect({
        "TenantSelectionProviderClient.useEffect": ()=>{
            if (!selectedTenantID && tenantOptions.length > 0 && entityType === 'global') {
                setTenant({
                    id: tenantOptions[0]?.value,
                    refresh: true
                });
            }
        }
    }["TenantSelectionProviderClient.useEffect"], [
        selectedTenantID,
        tenantOptions,
        entityType,
        setTenant
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
        "data-selected-tenant-id": selectedTenantID,
        "data-selected-tenant-title": selectedTenantLabel,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(Context, {
            value: {
                entityType,
                modified,
                options: tenantOptions,
                selectedTenantID,
                setEntityType,
                setModified,
                setTenant,
                syncTenants,
                updateTenants
            },
            children: children
        })
    });
};
const useTenantSelection = ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].use(Context);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-multi-tenant/dist/utilities/generateCookie.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "generateCookie",
    ()=>generateCookie
]);
const generateCookie = (args)=>{
    const { name, domain, expires, httpOnly, maxAge, path, returnCookieAsObject, sameSite, secure: secureArg, value } = args;
    let cookieString = `${name}=${value || ''}`;
    const cookieObject = {
        name,
        value
    };
    const secure = secureArg || sameSite === 'None';
    if (expires) {
        if (returnCookieAsObject) {
            cookieObject.expires = expires.toUTCString();
        } else {
            cookieString += `; Expires=${expires.toUTCString()}`;
        }
    }
    if (maxAge) {
        if (returnCookieAsObject) {
            cookieObject.maxAge = maxAge;
        } else {
            cookieString += `; Max-Age=${maxAge.toString()}`;
        }
    }
    if (domain) {
        if (returnCookieAsObject) {
            cookieObject.domain = domain;
        } else {
            cookieString += `; Domain=${domain}`;
        }
    }
    if (path) {
        if (returnCookieAsObject) {
            cookieObject.path = path;
        } else {
            cookieString += `; Path=${path}`;
        }
    }
    if (secure) {
        if (returnCookieAsObject) {
            cookieObject.secure = secure;
        } else {
            cookieString += `; Secure`;
        }
    }
    if (httpOnly) {
        if (returnCookieAsObject) {
            cookieObject.httpOnly = httpOnly;
        } else {
            cookieString += `; HttpOnly`;
        }
    }
    if (sameSite) {
        if (returnCookieAsObject) {
            cookieObject.sameSite = sameSite;
        } else {
            cookieString += `; SameSite=${sameSite}`;
        }
    }
    return returnCookieAsObject ? cookieObject : cookieString;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/defaults.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "defaults",
    ()=>defaults
]);
const defaults = {
    description: {
        maxLength: 150,
        minLength: 100
    },
    title: {
        maxLength: 60,
        minLength: 50
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaDescription/MetaDescriptionComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaDescriptionComponent",
    ()=>MetaDescriptionComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/defaults.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$LengthIndicator$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/LengthIndicator.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
const { maxLength: maxLengthDefault, minLength: minLengthDefault } = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaults"].description;
const MetaDescriptionComponent = (props)=>{
    const { field: { label, localized, maxLength: maxLengthFromProps, minLength: minLengthFromProps, required }, hasGenerateDescriptionFn, readOnly } = props;
    const { config: { routes: { api } } } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { getData } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const docInfo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const maxLength = maxLengthFromProps || maxLengthDefault;
    const minLength = minLengthFromProps || minLengthDefault;
    const { customComponents: { AfterInput, BeforeInput, Label } = {}, errorMessage, path, setValue, showError, value } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useField"])();
    const regenerateDescription = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "MetaDescriptionComponent.useCallback[regenerateDescription]": async ()=>{
            if (!hasGenerateDescriptionFn) {
                return;
            }
            const endpoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute: api,
                path: '/plugin-seo/generate-description'
            });
            const genDescriptionResponse = await fetch(endpoint, {
                body: JSON.stringify({
                    id: docInfo.id,
                    collectionSlug: docInfo.collectionSlug,
                    doc: getData(),
                    docPermissions: docInfo.docPermissions,
                    globalSlug: docInfo.globalSlug,
                    hasPublishPermission: docInfo.hasPublishPermission,
                    hasSavePermission: docInfo.hasSavePermission,
                    initialData: docInfo.initialData,
                    initialState: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["reduceToSerializableFields"])(docInfo.initialState ?? {}),
                    locale: typeof locale === 'object' ? locale?.code : locale,
                    title
                }),
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                method: 'POST'
            });
            const { result: generatedDescription } = await genDescriptionResponse.json();
            setValue(generatedDescription || '');
        }
    }["MetaDescriptionComponent.useCallback[regenerateDescription]"], [
        hasGenerateDescriptionFn,
        api,
        docInfo.id,
        docInfo.collectionSlug,
        docInfo.docPermissions,
        docInfo.globalSlug,
        docInfo.hasPublishPermission,
        docInfo.hasSavePermission,
        docInfo.initialData,
        docInfo.initialState,
        getData,
        locale,
        setValue,
        title
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        style: {
            marginBottom: '20px'
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                style: {
                    marginBottom: '5px',
                    position: 'relative'
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: "plugin-seo__field",
                        children: [
                            Label ?? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldLabel"], {
                                label: label,
                                localized: localized,
                                path: path,
                                required: required
                            }),
                            hasGenerateDescriptionFn && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                                children: [
                                    "  —  ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
                                        disabled: readOnly,
                                        onClick: ()=>{
                                            void regenerateDescription();
                                        },
                                        style: {
                                            background: 'none',
                                            backgroundColor: 'transparent',
                                            border: 'none',
                                            color: 'currentcolor',
                                            cursor: 'pointer',
                                            padding: 0,
                                            textDecoration: 'underline'
                                        },
                                        type: "button",
                                        children: t('plugin-seo:autoGenerate')
                                    })
                                ]
                            })
                        ]
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        style: {
                            color: '#9A9A9A'
                        },
                        children: [
                            t('plugin-seo:lengthTipDescription', {
                                maxLength,
                                minLength
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("a", {
                                href: "https://developers.google.com/search/docs/advanced/appearance/snippet#meta-descriptions",
                                rel: "noopener noreferrer",
                                target: "_blank",
                                children: t('plugin-seo:bestPractices')
                            })
                        ]
                    })
                ]
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    marginBottom: '10px',
                    position: 'relative'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["TextareaInput"], {
                    AfterInput: AfterInput,
                    BeforeInput: BeforeInput,
                    Error: errorMessage,
                    onChange: setValue,
                    path: path,
                    readOnly: readOnly,
                    required: required,
                    showError: showError,
                    style: {
                        marginBottom: 0
                    },
                    value: value
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    alignItems: 'center',
                    display: 'flex',
                    width: '100%'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$LengthIndicator$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LengthIndicator"], {
                    maxLength: maxLength,
                    minLength: minLength,
                    text: value
                })
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaImage/MetaImageComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaImageComponent",
    ()=>MetaImageComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$Pill$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/Pill.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const MetaImageComponent = (props)=>{
    const { field: { admin: { allowCreate } = {}, label, localized, relationTo, required }, hasGenerateImageFn, readOnly } = props;
    const { config: { routes: { api }, serverURL }, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { customComponents: { Error, Label } = {}, filterOptions, path, setValue, showError, value } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useField"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { getData } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const docInfo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const regenerateImage = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "MetaImageComponent.useCallback[regenerateImage]": async ()=>{
            if (!hasGenerateImageFn) {
                return;
            }
            const endpoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute: api,
                path: '/plugin-seo/generate-image'
            });
            const genImageResponse = await fetch(endpoint, {
                body: JSON.stringify({
                    id: docInfo.id,
                    collectionSlug: docInfo.collectionSlug,
                    doc: getData(),
                    docPermissions: docInfo.docPermissions,
                    globalSlug: docInfo.globalSlug,
                    hasPublishPermission: docInfo.hasPublishPermission,
                    hasSavePermission: docInfo.hasSavePermission,
                    initialData: docInfo.initialData,
                    initialState: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["reduceToSerializableFields"])(docInfo.initialState ?? {}),
                    locale: typeof locale === 'object' ? locale?.code : locale,
                    title
                }),
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                method: 'POST'
            });
            const { result: generatedImage } = await genImageResponse.json();
            // string ids, number ids or nullish values
            let newValue = generatedImage;
            // non-nullish resolved relations
            if (typeof generatedImage === 'object' && generatedImage && 'id' in generatedImage) {
                newValue = generatedImage.id;
            }
            // coerce to an empty string for falsy (=empty) values
            setValue(newValue || '');
        }
    }["MetaImageComponent.useCallback[regenerateImage]"], [
        hasGenerateImageFn,
        api,
        docInfo.id,
        docInfo.collectionSlug,
        docInfo.docPermissions,
        docInfo.globalSlug,
        docInfo.hasPublishPermission,
        docInfo.hasSavePermission,
        docInfo.initialData,
        docInfo.initialState,
        getData,
        locale,
        setValue,
        title
    ]);
    const hasImage = Boolean(value);
    const collection = getEntityConfig({
        collectionSlug: relationTo
    });
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        style: {
            marginBottom: '20px'
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                style: {
                    marginBottom: '5px',
                    position: 'relative'
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: "plugin-seo__field",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["RenderCustomComponent"], {
                                CustomComponent: Label,
                                Fallback: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldLabel"], {
                                    label: label,
                                    localized: localized,
                                    path: path,
                                    required: required
                                })
                            }),
                            hasGenerateImageFn && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                                children: [
                                    "  —  ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
                                        disabled: readOnly,
                                        onClick: ()=>{
                                            void regenerateImage();
                                        },
                                        style: {
                                            background: 'none',
                                            backgroundColor: 'transparent',
                                            border: 'none',
                                            color: 'currentcolor',
                                            cursor: 'pointer',
                                            padding: 0,
                                            textDecoration: 'underline'
                                        },
                                        type: "button",
                                        children: t('plugin-seo:autoGenerate')
                                    })
                                ]
                            })
                        ]
                    }),
                    hasGenerateImageFn && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        style: {
                            color: '#9A9A9A'
                        },
                        children: t('plugin-seo:imageAutoGenerationTip')
                    })
                ]
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    marginBottom: '10px',
                    position: 'relative'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["UploadInput"], {
                    allowCreate: allowCreate !== false,
                    api: api,
                    collection: collection,
                    Error: Error,
                    filterOptions: filterOptions,
                    onChange: (incomingImage)=>{
                        if (incomingImage !== null) {
                            if (typeof incomingImage === 'object') {
                                const { id: incomingID } = incomingImage;
                                setValue(incomingID);
                            } else {
                                setValue(incomingImage);
                            }
                        } else {
                            setValue(null);
                        }
                    },
                    path: path,
                    readOnly: readOnly,
                    relationTo: relationTo,
                    required: required,
                    serverURL: serverURL,
                    showError: showError,
                    style: {
                        marginBottom: 0
                    },
                    value: value
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    alignItems: 'center',
                    display: 'flex',
                    width: '100%'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$Pill$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Pill"], {
                    backgroundColor: hasImage ? 'green' : 'red',
                    color: "white",
                    label: hasImage ? t('plugin-seo:good') : t('plugin-seo:noImage')
                })
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaTitle/MetaTitleComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaTitleComponent",
    ()=>MetaTitleComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/defaults.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$LengthIndicator$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/LengthIndicator.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
;
;
const { maxLength: maxLengthDefault, minLength: minLengthDefault } = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaults"].title;
const MetaTitleComponent = (props)=>{
    const { field: { label, localized, maxLength: maxLengthFromProps, minLength: minLengthFromProps, required }, hasGenerateTitleFn, readOnly } = props;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: { routes: { api } } } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { customComponents: { AfterInput, BeforeInput, Label } = {}, errorMessage, path, setValue, showError, value } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useField"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const { getData } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const docInfo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const minLength = minLengthFromProps || minLengthDefault;
    const maxLength = maxLengthFromProps || maxLengthDefault;
    const regenerateTitle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "MetaTitleComponent.useCallback[regenerateTitle]": async ()=>{
            if (!hasGenerateTitleFn) {
                return;
            }
            const endpoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute: api,
                path: '/plugin-seo/generate-title'
            });
            const genTitleResponse = await fetch(endpoint, {
                body: JSON.stringify({
                    id: docInfo.id,
                    collectionSlug: docInfo.collectionSlug,
                    doc: getData(),
                    docPermissions: docInfo.docPermissions,
                    globalSlug: docInfo.globalSlug,
                    hasPublishPermission: docInfo.hasPublishPermission,
                    hasSavePermission: docInfo.hasSavePermission,
                    initialData: docInfo.initialData,
                    initialState: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["reduceToSerializableFields"])(docInfo.initialState ?? {}),
                    locale: typeof locale === 'object' ? locale?.code : locale,
                    title
                }),
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                method: 'POST'
            });
            const { result: generatedTitle } = await genTitleResponse.json();
            setValue(generatedTitle || '');
        }
    }["MetaTitleComponent.useCallback[regenerateTitle]"], [
        hasGenerateTitleFn,
        api,
        docInfo.id,
        docInfo.collectionSlug,
        docInfo.docPermissions,
        docInfo.globalSlug,
        docInfo.hasPublishPermission,
        docInfo.hasSavePermission,
        docInfo.initialData,
        docInfo.initialState,
        getData,
        locale,
        setValue,
        title
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        style: {
            marginBottom: '20px'
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                style: {
                    marginBottom: '5px',
                    position: 'relative'
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: "plugin-seo__field",
                        children: [
                            Label ?? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FieldLabel"], {
                                label: label,
                                localized: localized,
                                path: path,
                                required: required
                            }),
                            hasGenerateTitleFn && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                                children: [
                                    "  —  ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("button", {
                                        disabled: readOnly,
                                        onClick: ()=>{
                                            void regenerateTitle();
                                        },
                                        style: {
                                            background: 'none',
                                            backgroundColor: 'transparent',
                                            border: 'none',
                                            color: 'currentcolor',
                                            cursor: 'pointer',
                                            padding: 0,
                                            textDecoration: 'underline'
                                        },
                                        type: "button",
                                        children: t('plugin-seo:autoGenerate')
                                    })
                                ]
                            })
                        ]
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        style: {
                            color: '#9A9A9A'
                        },
                        children: [
                            t('plugin-seo:lengthTipTitle', {
                                maxLength,
                                minLength
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("a", {
                                href: "https://developers.google.com/search/docs/advanced/appearance/title-link#page-titles",
                                rel: "noopener noreferrer",
                                target: "_blank",
                                children: t('plugin-seo:bestPractices')
                            }),
                            "."
                        ]
                    })
                ]
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    marginBottom: '10px',
                    position: 'relative'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["TextInput"], {
                    AfterInput: AfterInput,
                    BeforeInput: BeforeInput,
                    Error: errorMessage,
                    onChange: setValue,
                    path: path,
                    readOnly: readOnly,
                    required: required,
                    showError: showError,
                    style: {
                        marginBottom: 0
                    },
                    value: value
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    alignItems: 'center',
                    display: 'flex',
                    width: '100%'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$LengthIndicator$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LengthIndicator"], {
                    maxLength: maxLength,
                    minLength: minLength,
                    text: value
                })
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Overview/OverviewComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "OverviewComponent",
    ()=>OverviewComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/defaults.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const { description: { maxLength: maxDescDefault, minLength: minDescDefault }, title: { maxLength: maxTitleDefault, minLength: minTitleDefault } } = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaults"];
const OverviewComponent = ({ descriptionOverrides, descriptionPath: descriptionPathFromContext, imagePath: imagePathFromContext, titleOverrides, titlePath: titlePathFromContext })=>{
    const { getFields } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const descriptionPath = descriptionPathFromContext || 'meta.description';
    const titlePath = titlePathFromContext || 'meta.title';
    const imagePath = imagePathFromContext || 'meta.image';
    const [{ [descriptionPath]: { value: metaDesc } = {}, [imagePath]: { value: metaImage } = {}, [titlePath]: { value: metaTitle } = {} }] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAllFormFields"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [titleIsValid, setTitleIsValid] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [descIsValid, setDescIsValid] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const [imageIsValid, setImageIsValid] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    const minDesc = descriptionOverrides?.minLength || minDescDefault;
    const maxDesc = descriptionOverrides?.maxLength || maxDescDefault;
    const minTitle = titleOverrides?.minLength || minTitleDefault;
    const maxTitle = titleOverrides?.maxLength || maxTitleDefault;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "OverviewComponent.useEffect": ()=>{
            if (typeof metaTitle === 'string') {
                setTitleIsValid(metaTitle.length >= minTitle && metaTitle.length <= maxTitle);
            }
            if (typeof metaDesc === 'string') {
                setDescIsValid(metaDesc.length >= minDesc && metaDesc.length <= maxDesc);
            }
            setImageIsValid(Boolean(metaImage));
        }
    }["OverviewComponent.useEffect"], [
        metaTitle,
        metaDesc,
        metaImage
    ]);
    const testResults = [
        titleIsValid,
        descIsValid,
        imageIsValid
    ];
    const numberOfPasses = testResults.filter(Boolean).length;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
        style: {
            marginBottom: '20px'
        },
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
            children: t('plugin-seo:checksPassing', {
                current: numberOfPasses,
                max: testResults.length
            })
        })
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Preview/PreviewComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PreviewComponent",
    ()=>PreviewComponent
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
const PreviewComponent = (props)=>{
    const { descriptionPath: descriptionPathFromContext, hasGenerateURLFn, titlePath: titlePathFromContext } = props;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: { routes: { api } } } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const [fields] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAllFormFields"])();
    const { getData } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useForm"])();
    const docInfo = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentInfo"])();
    const { title } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useDocumentTitle"])();
    const descriptionPath = descriptionPathFromContext || 'meta.description';
    const titlePath = titlePathFromContext || 'meta.title';
    const { [descriptionPath]: { value: metaDescription } = {}, [titlePath]: { value: metaTitle } = {} } = fields;
    const [href, setHref] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PreviewComponent.useEffect": ()=>{
            const endpoint = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute: api,
                path: '/plugin-seo/generate-url'
            });
            const getHref = {
                "PreviewComponent.useEffect.getHref": async ()=>{
                    const genURLResponse = await fetch(endpoint, {
                        body: JSON.stringify({
                            id: docInfo.id,
                            collectionSlug: docInfo.collectionSlug,
                            doc: getData(),
                            docPermissions: docInfo.docPermissions,
                            globalSlug: docInfo.globalSlug,
                            hasPublishPermission: docInfo.hasPublishPermission,
                            hasSavePermission: docInfo.hasSavePermission,
                            initialData: docInfo.initialData,
                            initialState: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["reduceToSerializableFields"])(docInfo.initialState ?? {}),
                            locale: typeof locale === 'object' ? locale?.code : locale,
                            title
                        }),
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        method: 'POST'
                    });
                    const { result: newHref } = await genURLResponse.json();
                    setHref(newHref);
                }
            }["PreviewComponent.useEffect.getHref"];
            if (hasGenerateURLFn && !href) {
                void getHref();
            }
        }
    }["PreviewComponent.useEffect"], [
        fields,
        href,
        locale,
        docInfo,
        hasGenerateURLFn,
        getData,
        api,
        title
    ]);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        style: {
            marginBottom: '20px'
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                children: t('plugin-seo:preview')
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    color: '#9A9A9A',
                    marginBottom: '5px'
                },
                children: t('plugin-seo:previewDescription')
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                style: {
                    background: 'var(--theme-elevation-50)',
                    borderRadius: '5px',
                    boxShadow: '0px 0px 10px rgba(0, 0, 0, 0.1)',
                    maxWidth: '600px',
                    padding: '20px',
                    pointerEvents: 'none',
                    width: '100%'
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("a", {
                            href: href,
                            style: {
                                textDecoration: 'none'
                            },
                            children: href || 'https://...'
                        })
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("h4", {
                        style: {
                            margin: 0
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("a", {
                            href: "/",
                            style: {
                                textDecoration: 'none'
                            },
                            children: metaTitle
                        })
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("p", {
                        style: {
                            margin: 0
                        },
                        children: metaDescription
                    })
                ]
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/LengthIndicator.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LengthIndicator",
    ()=>LengthIndicator
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$Pill$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/Pill.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const LengthIndicator = (props)=>{
    const { maxLength = 0, minLength = 0, text } = props;
    const [labelStyle, setLabelStyle] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        backgroundColor: '',
        color: ''
    });
    const [label, setLabel] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])('');
    const [barWidth, setBarWidth] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LengthIndicator.useEffect": ()=>{
            const textLength = text?.length || 0;
            if (textLength === 0) {
                setLabel(t('plugin-seo:missing'));
                setLabelStyle({
                    backgroundColor: 'red',
                    color: 'white'
                });
                setBarWidth(0);
            } else {
                const progress = (textLength - minLength) / (maxLength - minLength);
                if (progress < 0) {
                    const ratioUntilMin = textLength / minLength;
                    if (ratioUntilMin > 0.9) {
                        setLabel(t('plugin-seo:almostThere'));
                        setLabelStyle({
                            backgroundColor: 'orange',
                            color: 'white'
                        });
                    } else {
                        setLabel(t('plugin-seo:tooShort'));
                        setLabelStyle({
                            backgroundColor: 'orangered',
                            color: 'white'
                        });
                    }
                    setBarWidth(ratioUntilMin);
                }
                if (progress >= 0 && progress <= 1) {
                    setLabel(t('plugin-seo:good'));
                    setLabelStyle({
                        backgroundColor: 'green',
                        color: 'white'
                    });
                    setBarWidth(progress);
                }
                if (progress > 1) {
                    setLabel(t('plugin-seo:tooLong'));
                    setLabelStyle({
                        backgroundColor: 'red',
                        color: 'white'
                    });
                    setBarWidth(1);
                }
            }
        }
    }["LengthIndicator.useEffect"], [
        minLength,
        maxLength,
        text,
        t
    ]);
    const textLength = text?.length || 0;
    const charsUntilMax = maxLength - textLength;
    const charsUntilMin = minLength - textLength;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        style: {
            alignItems: 'center',
            display: 'flex',
            width: '100%'
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$ui$2f$Pill$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Pill"], {
                backgroundColor: labelStyle.backgroundColor,
                color: labelStyle.color,
                label: label
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    flexShrink: 0,
                    lineHeight: 1,
                    marginRight: '10px',
                    whiteSpace: 'nowrap'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("small", {
                    children: [
                        t('plugin-seo:characterCount', {
                            current: text?.length || 0,
                            maxLength,
                            minLength
                        }),
                        (textLength === 0 || charsUntilMin > 0) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: t('plugin-seo:charactersToGo', {
                                characters: charsUntilMin
                            })
                        }),
                        charsUntilMin <= 0 && charsUntilMax >= 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: t('plugin-seo:charactersLeftOver', {
                                characters: charsUntilMax
                            })
                        }),
                        charsUntilMax < 0 && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                            children: t('plugin-seo:charactersTooMany', {
                                characters: charsUntilMax * -1
                            })
                        })
                    ]
                })
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                style: {
                    backgroundColor: '#F3F3F3',
                    height: '2px',
                    position: 'relative',
                    width: '100%'
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    style: {
                        backgroundColor: labelStyle.backgroundColor,
                        height: '100%',
                        left: 0,
                        position: 'absolute',
                        top: 0,
                        width: `${barWidth * 100}%`
                    }
                })
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/ui/Pill.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "Pill",
    ()=>Pill
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
const Pill = (props)=>{
    const { backgroundColor, color, label } = props;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
        style: {
            backgroundColor,
            borderRadius: '2px',
            color,
            flexShrink: 0,
            lineHeight: 1,
            marginRight: '10px',
            padding: '4px 6px',
            whiteSpace: 'nowrap'
        },
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("small", {
            children: label
        })
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/clientKeys.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "clientTranslationKeys",
    ()=>clientTranslationKeys
]);
function createClientTranslationKeys(keys) {
    return keys;
}
const clientTranslationKeys = createClientTranslationKeys([
    'authentication:account',
    'authentication:accountOfCurrentUser',
    'authentication:accountVerified',
    'authentication:alreadyActivated',
    'authentication:alreadyLoggedIn',
    'authentication:apiKey',
    'authentication:authenticated',
    'authentication:backToLogin',
    'authentication:beginCreateFirstUser',
    'authentication:changePassword',
    'authentication:checkYourEmailForPasswordReset',
    'authentication:confirmGeneration',
    'authentication:confirmPassword',
    'authentication:createFirstUser',
    'authentication:emailNotValid',
    'authentication:usernameNotValid',
    'authentication:emailOrUsername',
    'authentication:emailSent',
    'authentication:emailVerified',
    'authentication:enableAPIKey',
    'authentication:failedToUnlock',
    'authentication:forceUnlock',
    'authentication:forgotPassword',
    'authentication:forgotPasswordEmailInstructions',
    'authentication:forgotPasswordUsernameInstructions',
    'authentication:forgotPasswordQuestion',
    'authentication:generate',
    'authentication:generateNewAPIKey',
    'authentication:generatingNewAPIKeyWillInvalidate',
    'authentication:logBackIn',
    'authentication:loggedOutInactivity',
    'authentication:loggedOutSuccessfully',
    'authentication:loggingOut',
    'authentication:login',
    'authentication:logOut',
    'authentication:loggedIn',
    'authentication:loggedInChangePassword',
    'authentication:logout',
    'authentication:logoutUser',
    'authentication:logoutSuccessful',
    'authentication:newAPIKeyGenerated',
    'authentication:newPassword',
    'authentication:passed',
    'authentication:passwordResetSuccessfully',
    'authentication:resetPassword',
    'authentication:stayLoggedIn',
    'authentication:successfullyRegisteredFirstUser',
    'authentication:successfullyUnlocked',
    'authentication:username',
    'authentication:unableToVerify',
    'authentication:tokenRefreshSuccessful',
    'authentication:verified',
    'authentication:verifiedSuccessfully',
    'authentication:verify',
    'authentication:verifyUser',
    'authentication:youAreInactive',
    'dashboard:addWidget',
    'dashboard:deleteWidget',
    'dashboard:searchWidgets',
    'dashboard:editDashboard',
    'dashboard:editingDashboard',
    'dashboard:resetLayout',
    'dashboard:addButton',
    'dashboard:discardConfirmLabel',
    'dashboard:discardMessage',
    'dashboard:discardTitle',
    'dashboard:noItems',
    'error:autosaving',
    'error:correctInvalidFields',
    'error:deletingTitle',
    'error:documentNotFound',
    'error:emailOrPasswordIncorrect',
    'error:usernameOrPasswordIncorrect',
    'error:loadingDocument',
    'error:insufficientClipboardPermissions',
    'error:invalidClipboardData',
    'error:invalidRequestArgs',
    'error:invalidFileType',
    'error:logoutFailed',
    'error:noMatchedField',
    'error:notAllowedToAccessPage',
    'error:notAllowedToPerformAction',
    'error:previewing',
    'error:unableToCopy',
    'error:unableToDeleteCount',
    'error:unableToReindexCollection',
    'error:unableToUpdateCount',
    'error:unauthorized',
    'error:unauthorizedAdmin',
    'error:unknown',
    'error:unspecific',
    'error:unverifiedEmail',
    'error:userEmailAlreadyRegistered',
    'error:usernameAlreadyRegistered',
    'error:tokenNotProvided',
    'error:unPublishingDocument',
    'error:revertingDocument',
    'error:problemUploadingFile',
    'error:restoringTitle',
    'error:failedToSaveLayout',
    'error:failedToResetLayout',
    'fields:addLabel',
    'fields:addLink',
    'fields:addNew',
    'fields:addNewLabel',
    'fields:addRelationship',
    'fields:addUpload',
    'fields:block',
    'fields:blocks',
    'fields:blockType',
    'fields:chooseBetweenCustomTextOrDocument',
    'fields:customURL',
    'fields:chooseDocumentToLink',
    'fields:openInNewTab',
    'fields:enterURL',
    'fields:internalLink',
    'fields:chooseFromExisting',
    'fields:linkType',
    'fields:textToDisplay',
    'fields:searchForLanguage',
    'fields:collapseAll',
    'fields:editLink',
    'fields:editRelationship',
    'fields:itemsAndMore',
    'fields:labelRelationship',
    'fields:latitude',
    'fields:linkedTo',
    'fields:longitude',
    'fields:passwordsDoNotMatch',
    'fields:removeRelationship',
    'fields:removeUpload',
    'fields:saveChanges',
    'fields:searchForBlock',
    'fields:selectFieldsToEdit',
    'fields:showAll',
    'fields:swapRelationship',
    'fields:swapUpload',
    'fields:toggleBlock',
    'fields:uploadNewLabel',
    'folder:byFolder',
    'folder:browseByFolder',
    'folder:deleteFolder',
    'folder:folders',
    'folder:folderTypeDescription',
    'folder:folderName',
    'folder:itemsMovedToFolder',
    'folder:itemsMovedToRoot',
    'folder:itemHasBeenMoved',
    'folder:itemHasBeenMovedToRoot',
    'folder:moveFolder',
    'folder:movingFromFolder',
    'folder:moveItemsToFolderConfirmation',
    'folder:moveItemsToRootConfirmation',
    'folder:moveItemToFolderConfirmation',
    'folder:moveItemToRootConfirmation',
    'folder:noFolder',
    'folder:newFolder',
    'folder:renameFolder',
    'folder:searchByNameInFolder',
    'folder:selectFolderForItem',
    'general:all',
    'general:aboutToDeleteCount',
    'general:aboutToDelete',
    'general:aboutToPermanentlyDelete',
    'general:aboutToPermanentlyDeleteTrash',
    'general:aboutToRestore',
    'general:aboutToRestoreAsDraft',
    'general:aboutToRestoreAsDraftCount',
    'general:aboutToRestoreCount',
    'general:aboutToTrash',
    'general:aboutToTrashCount',
    'general:addBelow',
    'general:addFilter',
    'general:adminTheme',
    'general:allCollections',
    'general:and',
    'general:anotherUser',
    'general:anotherUserTakenOver',
    'general:applyChanges',
    'general:ascending',
    'general:automatic',
    'general:backToDashboard',
    'general:cancel',
    'general:changesNotSaved',
    'general:close',
    'general:collapse',
    'general:collections',
    'general:confirmMove',
    'general:yes',
    'general:no',
    'general:columns',
    'general:columnToSort',
    'general:confirm',
    'general:confirmCopy',
    'general:confirmDeletion',
    'general:confirmDuplication',
    'general:confirmReindex',
    'general:confirmReindexAll',
    'general:confirmReindexDescription',
    'general:confirmReindexDescriptionAll',
    'general:confirmRestoration',
    'general:copied',
    'general:clear',
    'general:clearAll',
    'general:copy',
    'general:copyField',
    'general:copyRow',
    'general:copyWarning',
    'general:copying',
    'general:create',
    'general:created',
    'general:createdAt',
    'general:createNew',
    'general:createNewLabel',
    'general:creating',
    'general:creatingNewLabel',
    'general:currentlyEditing',
    'general:custom',
    'general:dark',
    'general:dashboard',
    'general:delete',
    'general:deleted',
    'general:deletedAt',
    'general:deletePermanently',
    'general:deleteLabel',
    'general:deletedSuccessfully',
    'general:deletedCountSuccessfully',
    'general:deleting',
    'general:descending',
    'general:depth',
    'general:deselectAllRows',
    'general:document',
    'general:documentIsTrashed',
    'general:documentLocked',
    'general:documentModified',
    'general:documentOutOfDate',
    'general:documents',
    'general:duplicate',
    'general:duplicateWithoutSaving',
    'general:edit',
    'general:editAll',
    'general:editing',
    'general:editingLabel',
    'general:editingTakenOver',
    'general:editLabel',
    'general:editedSince',
    'general:email',
    'general:emailAddress',
    'general:emptyTrash',
    'general:emptyTrashLabel',
    'general:enterAValue',
    'general:error',
    'general:errors',
    'general:fallbackToDefaultLocale',
    'general:false',
    'general:filters',
    'general:filterWhere',
    'general:globals',
    'general:goBack',
    'general:groupByLabel',
    'general:isEditing',
    'general:item',
    'general:items',
    'general:language',
    'general:lastModified',
    'general:layout',
    'general:leaveAnyway',
    'general:leaveWithoutSaving',
    'general:light',
    'general:livePreview',
    'general:lock',
    'general:exitLivePreview',
    'general:loading',
    'general:locale',
    'general:locales',
    'general:menu',
    'general:moreOptions',
    'general:move',
    'general:moveConfirm',
    'general:moveCount',
    'general:moveDown',
    'general:moveUp',
    'general:moving',
    'general:movingCount',
    'general:name',
    'general:next',
    'general:newLabel',
    'general:noDateSelected',
    'general:noFiltersSet',
    'general:noLabel',
    'general:none',
    'general:noOptions',
    'general:noResults',
    'general:noResultsDescription',
    'general:noResultsFound',
    'general:notFound',
    'general:nothingFound',
    'general:noTrashResults',
    'general:noUpcomingEventsScheduled',
    'general:noValue',
    'general:of',
    'general:open',
    'general:openInNewWindow',
    'general:only',
    'general:or',
    'general:order',
    'general:overwriteExistingData',
    'general:pageNotFound',
    'general:password',
    'general:pasteField',
    'general:pasteRow',
    'general:payloadSettings',
    'general:permanentlyDelete',
    'general:permanentlyDeletedCountSuccessfully',
    'general:perPage',
    'general:previous',
    'general:reindex',
    'general:reindexingAll',
    'general:reloadDocument',
    'general:remove',
    'general:rename',
    'general:reset',
    'general:resetPreferences',
    'general:resetPreferencesDescription',
    'general:resettingPreferences',
    'general:restore',
    'general:restoreAsPublished',
    'general:restoredCountSuccessfully',
    'general:restoring',
    'general:row',
    'general:rows',
    'general:save',
    'general:saveChanges',
    'general:schedulePublishFor',
    'general:saving',
    'general:searchBy',
    'general:select',
    'general:selectAll',
    'general:selectAllRows',
    'general:selectedCount',
    'general:selectLabel',
    'general:selectValue',
    'general:showAllLabel',
    'general:sorryNotFound',
    'general:sort',
    'general:sortByLabelDirection',
    'general:stayOnThisPage',
    'general:submissionSuccessful',
    'general:submit',
    'general:submitting',
    'general:success',
    'general:successfullyCreated',
    'general:successfullyDuplicated',
    'general:successfullyReindexed',
    'general:takeOver',
    'general:thisLanguage',
    'general:time',
    'general:timezone',
    'general:titleDeleted',
    'general:titleTrashed',
    'general:titleRestored',
    'general:trash',
    'general:trashedCountSuccessfully',
    'general:import',
    'general:export',
    'general:allLocales',
    'general:true',
    'general:upcomingEvents',
    'general:users',
    'general:user',
    'general:username',
    'general:unauthorized',
    'general:unlock',
    'general:unsavedChanges',
    'general:unsavedChangesDuplicate',
    'general:untitled',
    'general:updatedAt',
    'general:updatedLabelSuccessfully',
    'general:updatedCountSuccessfully',
    'general:updateForEveryone',
    'general:updatedSuccessfully',
    'general:updating',
    'general:value',
    'general:viewing',
    'general:viewReadOnly',
    'general:uploading',
    'general:uploadingBulk',
    'general:welcome',
    'localization:localeToPublish',
    'localization:copyToLocale',
    'localization:copyFromTo',
    'localization:selectedLocales',
    'localization:selectLocaleToCopy',
    'localization:selectLocaleToDuplicate',
    'localization:cannotCopySameLocale',
    'localization:copyFrom',
    'localization:copyTo',
    'operators:equals',
    'operators:exists',
    'operators:isNotIn',
    'operators:isIn',
    'operators:contains',
    'operators:isLike',
    'operators:isNotLike',
    'operators:isNotEqualTo',
    'operators:near',
    'operators:isGreaterThan',
    'operators:isLessThan',
    'operators:isGreaterThanOrEqualTo',
    'operators:isLessThanOrEqualTo',
    'operators:within',
    'operators:intersects',
    'upload:addFile',
    'upload:addFiles',
    'upload:bulkUpload',
    'upload:crop',
    'upload:cropToolDescription',
    'upload:dragAndDrop',
    'upload:editImage',
    'upload:fileToUpload',
    'upload:filesToUpload',
    'upload:focalPoint',
    'upload:focalPointDescription',
    'upload:height',
    'upload:pasteURL',
    'upload:previewSizes',
    'upload:selectCollectionToBrowse',
    'upload:selectFile',
    'upload:setCropArea',
    'upload:setFocalPoint',
    'upload:sizesFor',
    'upload:sizes',
    'upload:width',
    'upload:fileName',
    'upload:fileSize',
    'upload:noFile',
    'upload:download',
    'validation:emailAddress',
    'validation:enterNumber',
    'validation:fieldHasNo',
    'validation:greaterThanMax',
    'validation:invalidInput',
    'validation:invalidSelection',
    'validation:invalidSelections',
    'validation:latitudeOutOfBounds',
    'validation:lessThanMin',
    'validation:limitReached',
    'validation:longitudeOutOfBounds',
    'validation:invalidBlock',
    'validation:invalidBlocks',
    'validation:longerThanMin',
    'validation:notValidDate',
    'validation:required',
    'validation:requiresAtLeast',
    'validation:requiresNoMoreThan',
    'validation:requiresTwoNumbers',
    'validation:shorterThanMax',
    'validation:trueOrFalse',
    'validation:timezoneRequired',
    'validation:username',
    'validation:validUploadID',
    'version:aboutToPublishSelection',
    'version:aboutToRestore',
    'version:aboutToRestoreGlobal',
    'version:aboutToRevertToPublished',
    'version:aboutToUnpublish',
    'version:aboutToUnpublishIn',
    'version:aboutToUnpublishSelection',
    'version:autosave',
    'version:autosavedSuccessfully',
    'version:autosavedVersion',
    'version:versionAgo',
    'version:moreVersions',
    'version:changed',
    'version:changedFieldsCount',
    'version:confirmRevertToSaved',
    'version:compareVersions',
    'version:comparingAgainst',
    'version:currentlyViewing',
    'version:confirmPublish',
    'version:confirmUnpublish',
    'version:confirmVersionRestoration',
    'version:currentDraft',
    'version:currentPublishedVersion',
    'version:currentlyPublished',
    'version:draft',
    'version:draftHasPublishedVersion',
    'version:draftSavedSuccessfully',
    'version:lastSavedAgo',
    'version:modifiedOnly',
    'version:noFurtherVersionsFound',
    'version:noLabelGroup',
    'version:noRowsFound',
    'version:noRowsSelected',
    'version:preview',
    'version:previouslyDraft',
    'version:previouslyPublished',
    'version:previousVersion',
    'version:problemRestoringVersion',
    'version:publish',
    'version:publishAllLocales',
    'version:publishChanges',
    'version:published',
    'version:publishIn',
    'version:publishing',
    'version:restoreAsDraft',
    'version:restoredSuccessfully',
    'version:restoreThisVersion',
    'version:restoring',
    'version:reverting',
    'version:revertUnsuccessful',
    'version:revertToPublished',
    'version:saveDraft',
    'version:scheduledSuccessfully',
    'version:schedulePublish',
    'version:selectLocales',
    'version:selectVersionToCompare',
    'version:showLocales',
    'version:specificVersion',
    'version:status',
    'version:type',
    'version:unpublish',
    'version:unpublished',
    'version:unpublishIn',
    'version:unpublishing',
    'version:unpublishedSuccessfully',
    'version:versionID',
    'version:version',
    'version:versions',
    'version:viewingVersion',
    'version:viewingVersionGlobal',
    'version:viewingVersions',
    'version:viewingVersionsGlobal'
]);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/importDateFNSLocale.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "importDateFNSLocale",
    ()=>importDateFNSLocale
]);
const importDateFNSLocale = async (locale)=>{
    let result;
    switch(locale){
        case 'ar':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ar.js [app-client] (ecmascript, async loader)")).ar;
            break;
        case 'az':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/az.js [app-client] (ecmascript, async loader)")).az;
            break;
        case 'bg':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bg.js [app-client] (ecmascript, async loader)")).bg;
            break;
        case 'bn-BD':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn.js [app-client] (ecmascript, async loader)")).bn;
            break;
        case 'bn-IN':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/bn.js [app-client] (ecmascript, async loader)")).bn;
            break;
        case 'ca':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ca.js [app-client] (ecmascript, async loader)")).ca;
            break;
        case 'cs':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/cs.js [app-client] (ecmascript, async loader)")).cs;
            break;
        case 'da':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/da.js [app-client] (ecmascript, async loader)")).da;
            break;
        case 'de':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/de.js [app-client] (ecmascript, async loader)")).de;
            break;
        case 'en-US':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/en-US.js [app-client] (ecmascript, async loader)")).enUS;
            break;
        case 'es':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/es.js [app-client] (ecmascript, async loader)")).es;
            break;
        case 'et':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/et.js [app-client] (ecmascript, async loader)")).et;
            break;
        case 'fa-IR':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/fa-IR.js [app-client] (ecmascript, async loader)")).faIR;
            break;
        case 'fr':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/fr.js [app-client] (ecmascript, async loader)")).fr;
            break;
        case 'he':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/he.js [app-client] (ecmascript, async loader)")).he;
            break;
        case 'hr':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/hr.js [app-client] (ecmascript, async loader)")).hr;
            break;
        case 'hu':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/hu.js [app-client] (ecmascript, async loader)")).hu;
            break;
        case 'id':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/id.js [app-client] (ecmascript, async loader)")).id;
            break;
        case 'is':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/is.js [app-client] (ecmascript, async loader)")).is;
            break;
        case 'it':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/it.js [app-client] (ecmascript, async loader)")).it;
            break;
        case 'ja':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ja.js [app-client] (ecmascript, async loader)")).ja;
            break;
        case 'ko':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ko.js [app-client] (ecmascript, async loader)")).ko;
            break;
        case 'lt':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lt.js [app-client] (ecmascript, async loader)")).lt;
            break;
        case 'lv':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/lv.js [app-client] (ecmascript, async loader)")).lv;
            break;
        case 'nb':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/nb.js [app-client] (ecmascript, async loader)")).nb;
            break;
        case 'nl':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/nl.js [app-client] (ecmascript, async loader)")).nl;
            break;
        case 'pl':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/pl.js [app-client] (ecmascript, async loader)")).pl;
            break;
        case 'pt':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/pt.js [app-client] (ecmascript, async loader)")).pt;
            break;
        case 'ro':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ro.js [app-client] (ecmascript, async loader)")).ro;
            break;
        case 'rs':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/sr.js [app-client] (ecmascript, async loader)")).sr;
            break;
        case 'rs-Latin':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/sr-Latn.js [app-client] (ecmascript, async loader)")).srLatn;
            break;
        case 'ru':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ru.js [app-client] (ecmascript, async loader)")).ru;
            break;
        case 'sk':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/sk.js [app-client] (ecmascript, async loader)")).sk;
            break;
        case 'sl-SI':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/sl.js [app-client] (ecmascript, async loader)")).sl;
            break;
        case 'sv':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/sv.js [app-client] (ecmascript, async loader)")).sv;
            break;
        case 'ta':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/ta.js [app-client] (ecmascript, async loader)")).ta;
            break;
        case 'th':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/th.js [app-client] (ecmascript, async loader)")).th;
            break;
        case 'tr':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/tr.js [app-client] (ecmascript, async loader)")).tr;
            break;
        case 'uk':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/uk.js [app-client] (ecmascript, async loader)")).uk;
            break;
        case 'vi':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/vi.js [app-client] (ecmascript, async loader)")).vi;
            break;
        case 'zh-CN':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/zh-CN.js [app-client] (ecmascript, async loader)")).zhCN;
            break;
        case 'zh-TW':
            result = (await __turbopack_context__.A("[project]/blueprints/payload-next-multisite/app/node_modules/date-fns/locale/zh-TW.js [app-client] (ecmascript, async loader)")).zhTW;
            break;
    }
    // @ts-expect-error - I'm not sure if this is still necessary.
    if (result?.default) {
        // @ts-expect-error - I'm not sure if this is still necessary.
        return result.default;
    }
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/deepMergeSimple.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Very simple, but fast deepMerge implementation. Only deepMerges objects, not arrays and clones everything.
 * Do not use this if your object contains any complex objects like React Components, or if you would like to combine Arrays.
 * If you only have simple objects and need a fast deepMerge, this is the function for you.
 *
 * obj2 takes precedence over obj1 - thus if obj2 has a key that obj1 also has, obj2's value will be used.
 *
 * @param obj1 base object
 * @param obj2 object to merge "into" obj1
 */ __turbopack_context__.s([
    "deepMergeSimple",
    ()=>deepMergeSimple
]);
function deepMergeSimple(obj1, obj2) {
    const output = {
        ...obj1
    };
    for(const key in obj2){
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
            continue;
        }
        if (Object.prototype.hasOwnProperty.call(obj2, key)) {
            // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
            if (typeof obj2[key] === 'object' && !Array.isArray(obj2[key]) && obj1[key]) {
                // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
                output[key] = deepMergeSimple(obj1[key], obj2[key]);
            } else {
                // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
                output[key] = obj2[key];
            }
        }
    }
    return output;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getTranslation",
    ()=>getTranslation
]);
const getTranslation = (label, /**
   * @todo type as I18nClient in 4.0
   */ i18n)=>{
    // If it's a Record, look for translation. If string or React Element, pass through
    if (typeof label === 'object' && !Object.prototype.hasOwnProperty.call(label, '$$typeof')) {
        // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
        if (label[i18n.language]) {
            // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
            return label[i18n.language];
        }
        let fallbacks = [];
        if (typeof i18n.fallbackLanguage === 'string') {
            fallbacks = [
                i18n.fallbackLanguage
            ];
        } else if (Array.isArray(i18n.fallbackLanguage)) {
            fallbacks = i18n.fallbackLanguage;
        }
        const fallbackLang = fallbacks.find((language)=>label[language]);
        // @ts-expect-error - vestiges of when tsconfig was not strict. Feel free to improve
        return fallbackLang && label[fallbackLang] ? label[fallbackLang] : label[Object.keys(label)[0]];
    }
    if (typeof label === 'function') {
        return label({
            i18n: i18n,
            t: i18n.t
        });
    }
    // If it's a React Element or string, then we should just pass it through
    return label;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslationsByContext.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getTranslationsByContext",
    ()=>getTranslationsByContext
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$clientKeys$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/clientKeys.js [app-client] (ecmascript)");
;
function filterKeys(obj, parentGroupKey = '', keys) {
    const result = {};
    for (const [namespaceKey, value] of Object.entries(obj)){
        // Skip $schema key
        if (namespaceKey === '$schema') {
            result[namespaceKey] = value;
            continue;
        }
        if (typeof value === 'object') {
            const filteredObject = filterKeys(value, namespaceKey, keys);
            if (Object.keys(filteredObject).length > 0) {
                result[namespaceKey] = filteredObject;
            }
        } else {
            for (const key of keys){
                const [groupKey, selector] = key.split(':');
                if (parentGroupKey === groupKey) {
                    if (namespaceKey === selector) {
                        result[selector] = value;
                    } else {
                        const pluralKeys = [
                            'zero',
                            'one',
                            'two',
                            'few',
                            'many',
                            'other'
                        ];
                        pluralKeys.forEach((pluralKey)=>{
                            if (namespaceKey === `${selector}_${pluralKey}`) {
                                result[`${selector}_${pluralKey}`] = value;
                            }
                        });
                    }
                }
            }
        }
    }
    return result;
}
function sortObject(obj) {
    const sortedObject = {};
    Object.keys(obj).sort().forEach((key)=>{
        if (typeof obj[key] === 'object') {
            sortedObject[key] = sortObject(obj[key]);
        } else {
            sortedObject[key] = obj[key];
        }
    });
    return sortedObject;
}
const getTranslationsByContext = (selectedLanguage, context)=>{
    if (context === 'client') {
        return sortObject(filterKeys(selectedLanguage.translations, '', __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$clientKeys$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["clientTranslationKeys"]));
    } else {
        return selectedLanguage.translations;
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/init.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getTranslationString",
    ()=>getTranslationString,
    "initI18n",
    ()=>initI18n,
    "t",
    ()=>t
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$importDateFNSLocale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/importDateFNSLocale.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$deepMergeSimple$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/deepMergeSimple.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslationsByContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslationsByContext.js [app-client] (ecmascript)");
;
;
;
const getTranslationString = ({ count, key, translations })=>{
    const keys = key.split(':');
    let keySuffix = '';
    const translation = keys.reduce((acc, key, index)=>{
        if (typeof acc === 'string') {
            return acc;
        }
        if (typeof count === 'number') {
            if (count === 0 && `${key}_zero` in acc) {
                keySuffix = '_zero';
            } else if (count === 1 && `${key}_one` in acc) {
                keySuffix = '_one';
            } else if (count === 2 && `${key}_two` in acc) {
                keySuffix = '_two';
            } else if (count > 5 && `${key}_many` in acc) {
                keySuffix = '_many';
            } else if (count > 2 && count <= 5 && `${key}_few` in acc) {
                keySuffix = '_few';
            } else if (`${key}_other` in acc) {
                keySuffix = '_other';
            }
        }
        let keyToUse = key;
        if (index === keys.length - 1 && keySuffix) {
            keyToUse = `${key}${keySuffix}`;
        }
        if (acc && keyToUse in acc) {
            return acc[keyToUse];
        }
        return undefined;
    }, translations);
    if (!translation) {
        console.log('key not found:', key);
    }
    return translation || key;
};
/**
 * @function replaceVars
 *
 * Replaces variables in a translation string with values from an object
 *
 * @returns string
 */ const replaceVars = ({ translationString, vars })=>{
    const parts = translationString.split(/(\{\{.*?\}\})/);
    return parts.map((part)=>{
        if (part.startsWith('{{') && part.endsWith('}}')) {
            const placeholder = part.substring(2, part.length - 2).trim();
            const value = vars[placeholder];
            return value !== undefined && value !== null ? value : part;
        } else {
            return part;
        }
    }).join('');
};
function t({ key, translations, vars }) {
    let translationString = getTranslationString({
        count: typeof vars?.count === 'number' ? vars.count : undefined,
        key,
        translations
    });
    if (vars) {
        translationString = replaceVars({
            translationString,
            vars
        });
    }
    if (!translationString) {
        translationString = key;
    }
    return translationString;
}
const initTFunction = (args)=>{
    const { config, language, translations } = args;
    const mergedTranslations = language && config?.translations?.[language] ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$deepMergeSimple$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["deepMergeSimple"])(translations, config.translations[language]) : translations;
    return {
        t: (key, vars)=>{
            return t({
                key,
                translations: mergedTranslations,
                vars
            });
        },
        translations: mergedTranslations
    };
};
function memoize(fn, keys) {
    const cacheMap = new Map();
    const memoized = async (args)=>{
        const cacheKey = keys.reduce((acc, key)=>acc + String(args[key]), '');
        if (!cacheMap.has(cacheKey)) {
            const result = await fn(args);
            cacheMap.set(cacheKey, result);
        }
        return cacheMap.get(cacheKey);
    };
    return memoized;
}
const initI18n = memoize(async ({ config, context, language = config.fallbackLanguage })=>{
    if (!language || !config.supportedLanguages?.[language]) {
        throw new Error(`Language ${language} not supported`);
    }
    const translations = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslationsByContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslationsByContext"])(config.supportedLanguages?.[language], context);
    const { t, translations: mergedTranslations } = initTFunction({
        config: config,
        language: language || config.fallbackLanguage,
        translations: translations
    });
    const dateFNSKey = config.supportedLanguages[language]?.dateFNSKey || 'en-US';
    const dateFNS = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$importDateFNSLocale$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["importDateFNSLocale"])(dateFNSKey);
    const i18n = {
        dateFNS,
        dateFNSKey,
        fallbackLanguage: config.fallbackLanguage,
        language: language || config.fallbackLanguage,
        t,
        translations: mergedTranslations
    };
    return i18n;
}, [
    'language',
    'context'
]);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/languages.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "acceptedLanguages",
    ()=>acceptedLanguages,
    "extractHeaderLanguage",
    ()=>extractHeaderLanguage,
    "rtlLanguages",
    ()=>rtlLanguages
]);
const rtlLanguages = [
    'ar',
    'fa',
    'he'
];
const acceptedLanguages = [
    'ar',
    'az',
    'bg',
    'bn-BD',
    'bn-IN',
    'ca',
    'cs',
    'bn-BD',
    'bn-IN',
    'da',
    'de',
    'en',
    'es',
    'et',
    'fa',
    'fr',
    'he',
    'hr',
    'hu',
    'hy',
    'id',
    'is',
    'it',
    'ja',
    'ko',
    'lt',
    'lv',
    'my',
    'nb',
    'nl',
    'pl',
    'pt',
    'ro',
    'rs',
    'rs-latin',
    'ru',
    'sk',
    'sl',
    'sv',
    'ta',
    'th',
    'tr',
    'uk',
    'vi',
    'zh',
    'zh-TW'
];
function parseAcceptLanguage(acceptLanguageHeader) {
    return acceptLanguageHeader.split(',').map((lang)=>{
        const [language, quality] = lang.trim().split(';q=');
        return {
            language,
            quality: quality ? parseFloat(quality) : 1
        };
    }).sort((a, b)=>b.quality - a.quality) // Sort by quality, highest to lowest
    ;
}
function extractHeaderLanguage(acceptLanguageHeader) {
    const parsedHeader = parseAcceptLanguage(acceptLanguageHeader);
    let matchedLanguage;
    for (const { language } of parsedHeader){
        if (matchedLanguage) {
            break;
        }
        if (acceptedLanguages.includes(language)) {
            matchedLanguage = language;
            break;
        }
        const baseLanguage = language.split('-')[0];
        if (acceptedLanguages.includes(baseLanguage)) {
            matchedLanguage = baseLanguage;
            break;
        }
    }
    return matchedLanguage;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$buffer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/buffer/index.js [app-client] (ecmascript)");
var MACHINE_ID = Math.floor(Math.random() * 0xFFFFFF);
var index = ObjectID.index = parseInt(Math.random() * 0xFFFFFF, 10);
var pid = (typeof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"] === 'undefined' || typeof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].pid !== 'number' ? Math.floor(Math.random() * 100000) : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].pid) % 0xFFFF;
// <https://github.com/williamkapke/bson-objectid/pull/51>
// Attempt to fallback Buffer if _Buffer is undefined (e.g. for Node.js).
// Worst case fallback to null and handle with null checking before using.
var BufferCtr = (()=>{
    try {
        return _Buffer;
    } catch (_) {
        try {
            return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$buffer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Buffer"];
        } catch (_) {
            return null;
        }
    }
})();
/**
 * Determine if an object is Buffer
 *
 * Author:   Feross Aboukhadijeh <feross@feross.org> <http://feross.org>
 * License:  MIT
 *
 */ var isBuffer = function(obj) {
    return !!(obj != null && obj.constructor && typeof obj.constructor.isBuffer === 'function' && obj.constructor.isBuffer(obj));
};
// Precomputed hex table enables speedy hex string conversion
var hexTable = [];
for(var i = 0; i < 256; i++){
    hexTable[i] = (i <= 15 ? '0' : '') + i.toString(16);
}
// Regular expression that checks for hex value
var checkForHexRegExp = new RegExp('^[0-9a-fA-F]{24}$');
// Lookup tables
var decodeLookup = [];
i = 0;
while(i < 10)decodeLookup[0x30 + i] = i++;
while(i < 16)decodeLookup[0x41 - 10 + i] = decodeLookup[0x61 - 10 + i] = i++;
/**
 * Create a new immutable ObjectID instance
 *
 * @class Represents the BSON ObjectID type
 * @param {String|Number} id Can be a 24 byte hex string, 12 byte binary string or a Number.
 * @return {Object} instance of ObjectID.
 */ function ObjectID(id) {
    if (!(this instanceof ObjectID)) return new ObjectID(id);
    if (id && (id instanceof ObjectID || id._bsontype === "ObjectID")) return id;
    this._bsontype = 'ObjectID';
    // The most common usecase (blank id, new objectId instance)
    if (id == null || typeof id === 'number') {
        // Generate a new id
        this.id = this.generate(id);
        // Return the object
        return;
    }
    // Check if the passed in id is valid
    var valid = ObjectID.isValid(id);
    // Throw an error if it's not a valid setup
    if (!valid && id != null) {
        throw new Error('Argument passed in must be a single String of 12 bytes or a string of 24 hex characters');
    } else if (valid && typeof id === 'string' && id.length === 24) {
        return ObjectID.createFromHexString(id);
    } else if (id != null && id.length === 12) {
        // assume 12 byte string
        this.id = id;
    } else if (id != null && typeof id.toHexString === 'function') {
        // Duck-typing to support ObjectId from different npm packages
        return id;
    } else {
        throw new Error('Argument passed in must be a single String of 12 bytes or a string of 24 hex characters');
    }
}
module.exports = ObjectID;
ObjectID.default = ObjectID;
/**
 * Creates an ObjectID from a second based number, with the rest of the ObjectID zeroed out. Used for comparisons or sorting the ObjectID.
 *
 * @param {Number} time an integer number representing a number of seconds.
 * @return {ObjectID} return the created ObjectID
 * @api public
 */ ObjectID.createFromTime = function(time) {
    time = parseInt(time, 10) % 0xFFFFFFFF;
    return new ObjectID(hex(8, time) + "0000000000000000");
};
/**
 * Creates an ObjectID from a hex string representation of an ObjectID.
 *
 * @param {String} hexString create a ObjectID from a passed in 24 byte hexstring.
 * @return {ObjectID} return the created ObjectID
 * @api public
 */ ObjectID.createFromHexString = function(hexString) {
    // Throw an error if it's not a valid setup
    if (typeof hexString === 'undefined' || hexString != null && hexString.length !== 24) {
        throw new Error('Argument passed in must be a single String of 12 bytes or a string of 24 hex characters');
    }
    // Calculate lengths
    var data = '';
    var i = 0;
    while(i < 24){
        data += String.fromCharCode(decodeLookup[hexString.charCodeAt(i++)] << 4 | decodeLookup[hexString.charCodeAt(i++)]);
    }
    return new ObjectID(data);
};
/**
 * Checks if a value is a valid bson ObjectId
 *
 * @param {String} objectid Can be a 24 byte hex string or an instance of ObjectID.
 * @return {Boolean} return true if the value is a valid bson ObjectID, return false otherwise.
 * @api public
 *
 * THE NATIVE DOCUMENTATION ISN'T CLEAR ON THIS GUY!
 * http://mongodb.github.io/node-mongodb-native/api-bson-generated/objectid.html#objectid-isvalid
 */ ObjectID.isValid = function(id) {
    if (id == null) return false;
    if (typeof id === 'number') {
        return true;
    }
    if (typeof id === 'string') {
        return id.length === 12 || id.length === 24 && checkForHexRegExp.test(id);
    }
    if (id instanceof ObjectID) {
        return true;
    }
    // <https://github.com/williamkapke/bson-objectid/issues/53>
    if (isBuffer(id)) {
        return ObjectID.isValid(id.toString('hex'));
    }
    // Duck-Typing detection of ObjectId like objects
    // <https://github.com/williamkapke/bson-objectid/pull/51>
    if (typeof id.toHexString === 'function') {
        if (BufferCtr && (id.id instanceof BufferCtr || typeof id.id === 'string')) {
            return id.id.length === 12 || id.id.length === 24 && checkForHexRegExp.test(id.id);
        }
    }
    return false;
};
ObjectID.prototype = {
    constructor: ObjectID,
    /**
   * Return the ObjectID id as a 24 byte hex string representation
   *
   * @return {String} return the 24 byte hex string representation.
   * @api public
   */ toHexString: function() {
        if (!this.id || !this.id.length) {
            throw new Error('invalid ObjectId, ObjectId.id must be either a string or a Buffer, but is [' + JSON.stringify(this.id) + ']');
        }
        if (this.id.length === 24) {
            return this.id;
        }
        if (isBuffer(this.id)) {
            return this.id.toString('hex');
        }
        var hexString = '';
        for(var i = 0; i < this.id.length; i++){
            hexString += hexTable[this.id.charCodeAt(i)];
        }
        return hexString;
    },
    /**
   * Compares the equality of this ObjectID with `otherID`.
   *
   * @param {Object} otherId ObjectID instance to compare against.
   * @return {Boolean} the result of comparing two ObjectID's
   * @api public
   */ equals: function(otherId) {
        if (otherId instanceof ObjectID) {
            return this.toString() === otherId.toString();
        } else if (typeof otherId === 'string' && ObjectID.isValid(otherId) && otherId.length === 12 && isBuffer(this.id)) {
            return otherId === this.id.toString('binary');
        } else if (typeof otherId === 'string' && ObjectID.isValid(otherId) && otherId.length === 24) {
            return otherId.toLowerCase() === this.toHexString();
        } else if (typeof otherId === 'string' && ObjectID.isValid(otherId) && otherId.length === 12) {
            return otherId === this.id;
        } else if (otherId != null && (otherId instanceof ObjectID || otherId.toHexString)) {
            return otherId.toHexString() === this.toHexString();
        } else {
            return false;
        }
    },
    /**
   * Returns the generation date (accurate up to the second) that this ID was generated.
   *
   * @return {Date} the generation date
   * @api public
   */ getTimestamp: function() {
        var timestamp = new Date();
        var time;
        if (isBuffer(this.id)) {
            time = this.id[3] | this.id[2] << 8 | this.id[1] << 16 | this.id[0] << 24;
        } else {
            time = this.id.charCodeAt(3) | this.id.charCodeAt(2) << 8 | this.id.charCodeAt(1) << 16 | this.id.charCodeAt(0) << 24;
        }
        timestamp.setTime(Math.floor(time) * 1000);
        return timestamp;
    },
    /**
  * Generate a 12 byte id buffer used in ObjectID's
  *
  * @method
  * @param {number} [time] optional parameter allowing to pass in a second based timestamp.
  * @return {string} return the 12 byte id buffer string.
  */ generate: function(time) {
        if ('number' !== typeof time) {
            time = ~~(Date.now() / 1000);
        }
        //keep it in the ring!
        time = parseInt(time, 10) % 0xFFFFFFFF;
        var inc = next();
        return String.fromCharCode(time >> 24 & 0xFF, time >> 16 & 0xFF, time >> 8 & 0xFF, time & 0xFF, MACHINE_ID >> 16 & 0xFF, MACHINE_ID >> 8 & 0xFF, MACHINE_ID & 0xFF, pid >> 8 & 0xFF, pid & 0xFF, inc >> 16 & 0xFF, inc >> 8 & 0xFF, inc & 0xFF);
    }
};
function next() {
    return index = (index + 1) % 0xFFFFFF;
}
function hex(length, n) {
    n = n.toString(16);
    return n.length === length ? n : "00000000".substring(n.length, length) + n;
}
function buffer(str) {
    var i = 0, out = [];
    if (str.length === 24) for(; i < 24; out.push(parseInt(str[i] + str[i + 1], 16)), i += 2);
    else if (str.length === 12) for(; i < 12; out.push(str.charCodeAt(i)), i++);
    return out;
}
var inspect = Symbol && Symbol.for && Symbol.for('nodejs.util.inspect.custom') || 'inspect';
/**
 * Converts to a string representation of this Id.
 *
 * @return {String} return the 24 byte hex string representation.
 * @api private
 */ ObjectID.prototype[inspect] = function() {
    return "ObjectID(" + this + ")";
};
ObjectID.prototype.toJSON = ObjectID.prototype.toHexString;
ObjectID.prototype.toString = ObjectID.prototype.toHexString;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/clsx/dist/clsx.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

function r(e) {
    var o, t, f = "";
    if ("string" == typeof e || "number" == typeof e) f += e;
    else if ("object" == typeof e) if (Array.isArray(e)) {
        var n = e.length;
        for(o = 0; o < n; o++)e[o] && (t = r(e[o])) && (f && (f += " "), f += t);
    } else for(t in e)e[t] && (f && (f += " "), f += t);
    return f;
}
function e() {
    for(var e, o, t = 0, f = "", n = arguments.length; t < n; t++)(e = arguments[t]) && (o = r(e)) && (f && (f += " "), f += o);
    return f;
}
module.exports = e, module.exports.clsx = e;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/dequal/lite/index.mjs [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "dequal",
    ()=>dequal
]);
var has = Object.prototype.hasOwnProperty;
function dequal(foo, bar) {
    var ctor, len;
    if (foo === bar) return true;
    if (foo && bar && (ctor = foo.constructor) === bar.constructor) {
        if (ctor === Date) return foo.getTime() === bar.getTime();
        if (ctor === RegExp) return foo.toString() === bar.toString();
        if (ctor === Array) {
            if ((len = foo.length) === bar.length) {
                while(len-- && dequal(foo[len], bar[len]));
            }
            return len === -1;
        }
        if (!ctor || typeof foo === 'object') {
            len = 0;
            for(ctor in foo){
                if (has.call(foo, ctor) && ++len && !has.call(bar, ctor)) return false;
                if (!(ctor in bar) || !dequal(foo[ctor], bar[ctor])) return false;
            }
            return Object.keys(bar).length === len;
        }
    }
    return foo !== foo && bar !== bar;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/addClass.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>addClass
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$hasClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/hasClass.js [app-client] (ecmascript)");
;
function addClass(element, className) {
    if (element.classList) element.classList.add(className);
    else if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$hasClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(element, className)) if (typeof element.className === 'string') element.className = element.className + " " + className;
    else element.setAttribute('class', (element.className && element.className.baseVal || '') + " " + className);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/hasClass.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Checks if a given element has a CSS class.
 * 
 * @param element the element
 * @param className the CSS class name
 */ __turbopack_context__.s([
    "default",
    ()=>hasClass
]);
function hasClass(element, className) {
    if (element.classList) return !!className && element.classList.contains(className);
    return (" " + (element.className.baseVal || element.className) + " ").indexOf(" " + className + " ") !== -1;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/removeClass.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>removeClass
]);
function replaceClassName(origClass, classToRemove) {
    return origClass.replace(new RegExp("(^|\\s)" + classToRemove + "(?:\\s|$)", 'g'), '$1').replace(/\s+/g, ' ').replace(/^\s*|\s*$/g, '');
}
function removeClass(element, className) {
    if (element.classList) {
        element.classList.remove(className);
    } else if (typeof element.className === 'string') {
        element.className = replaceClassName(element.className, className);
    } else {
        element.setAttribute('class', replaceClassName(element.className && element.className.baseVal || '', className));
    }
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/fast-deep-equal/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

// do not edit .js files directly - edit src/index.jst
module.exports = function equal(a, b) {
    if (a === b) return true;
    if (a && b && typeof a == 'object' && typeof b == 'object') {
        if (a.constructor !== b.constructor) return false;
        var length, i, keys;
        if (Array.isArray(a)) {
            length = a.length;
            if (length != b.length) return false;
            for(i = length; i-- !== 0;)if (!equal(a[i], b[i])) return false;
            return true;
        }
        if (a.constructor === RegExp) return a.source === b.source && a.flags === b.flags;
        if (a.valueOf !== Object.prototype.valueOf) return a.valueOf() === b.valueOf();
        if (a.toString !== Object.prototype.toString) return a.toString() === b.toString();
        keys = Object.keys(a);
        length = keys.length;
        if (length !== Object.keys(b).length) return false;
        for(i = length; i-- !== 0;)if (!Object.prototype.hasOwnProperty.call(b, keys[i])) return false;
        for(i = length; i-- !== 0;){
            var key = keys[i];
            if (!equal(a[key], b[key])) return false;
        }
        return true;
    }
    // true if both NaN, false otherwise
    return a !== a && b !== b;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

const { normalizeIPv6, removeDotSegments, recomposeAuthority, normalizePercentEncoding, normalizePathEncoding, escapePreservingEscapes, reescapeHostDelimiters, isIPv4, nonSimpleDomain } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/lib/utils.js [app-client] (ecmascript)");
const { SCHEMES, getSchemeHandler } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/lib/schemes.js [app-client] (ecmascript)");
/**
 * @template {import('./types/index').URIComponent|string} T
 * @param {T} uri
 * @param {import('./types/index').Options} [options]
 * @returns {T}
 */ function normalize(uri, options) {
    if (typeof uri === 'string') {
        uri = normalizeString(uri, options);
    } else if (typeof uri === 'object') {
        uri = parse(serialize(uri, options), options);
    }
    return uri;
}
/**
 * @param {string} baseURI
 * @param {string} relativeURI
 * @param {import('./types/index').Options} [options]
 * @returns {string}
 */ function resolve(baseURI, relativeURI, options) {
    const schemelessOptions = options ? Object.assign({
        scheme: 'null'
    }, options) : {
        scheme: 'null'
    };
    const { parsed: baseParsed, malformedAuthorityOrPort: baseMalformed } = parseWithStatus(baseURI, schemelessOptions);
    const { parsed: relativeParsed, malformedAuthorityOrPort: relativeMalformed } = parseWithStatus(relativeURI, schemelessOptions);
    if (baseMalformed || relativeMalformed) {
        throw new Error(baseParsed.error || relativeParsed.error || 'URI is malformed.');
    }
    const resolved = resolveComponent(baseParsed, relativeParsed, schemelessOptions, true);
    schemelessOptions.skipEscape = true;
    return serialize(resolved, schemelessOptions);
}
/**
 * @param {import ('./types/index').URIComponent} base
 * @param {import ('./types/index').URIComponent} relative
 * @param {import('./types/index').Options} [options]
 * @param {boolean} [skipNormalization=false]
 * @returns {import ('./types/index').URIComponent}
 */ function resolveComponent(base, relative, options, skipNormalization) {
    /** @type {import('./types/index').URIComponent} */ const target = {};
    if (!skipNormalization) {
        base = parse(serialize(base, options), options); // normalize base component
        relative = parse(serialize(relative, options), options); // normalize relative component
    }
    options = options || {};
    if (!options.tolerant && relative.scheme) {
        target.scheme = relative.scheme;
        // target.authority = relative.authority;
        target.userinfo = relative.userinfo;
        target.host = relative.host;
        target.port = relative.port;
        target.path = removeDotSegments(relative.path || '');
        target.query = relative.query;
    } else {
        if (relative.userinfo !== undefined || relative.host !== undefined || relative.port !== undefined) {
            // target.authority = relative.authority;
            target.userinfo = relative.userinfo;
            target.host = relative.host;
            target.port = relative.port;
            target.path = removeDotSegments(relative.path || '');
            target.query = relative.query;
        } else {
            if (!relative.path) {
                target.path = base.path;
                if (relative.query !== undefined) {
                    target.query = relative.query;
                } else {
                    target.query = base.query;
                }
            } else {
                if (relative.path[0] === '/') {
                    target.path = removeDotSegments(relative.path);
                } else {
                    if ((base.userinfo !== undefined || base.host !== undefined || base.port !== undefined) && !base.path) {
                        target.path = '/' + relative.path;
                    } else if (!base.path) {
                        target.path = relative.path;
                    } else {
                        target.path = base.path.slice(0, base.path.lastIndexOf('/') + 1) + relative.path;
                    }
                    target.path = removeDotSegments(target.path);
                }
                target.query = relative.query;
            }
            // target.authority = base.authority;
            target.userinfo = base.userinfo;
            target.host = base.host;
            target.port = base.port;
        }
        target.scheme = base.scheme;
    }
    target.fragment = relative.fragment;
    return target;
}
/**
 * @param {import ('./types/index').URIComponent|string} uriA
 * @param {import ('./types/index').URIComponent|string} uriB
 * @param {import ('./types/index').Options} options
 * @returns {boolean}
 */ function equal(uriA, uriB, options) {
    const normalizedA = normalizeComparableURI(uriA, options);
    const normalizedB = normalizeComparableURI(uriB, options);
    return normalizedA !== undefined && normalizedB !== undefined && normalizedA.toLowerCase() === normalizedB.toLowerCase();
}
/**
 * @param {Readonly<import('./types/index').URIComponent>} cmpts
 * @param {import('./types/index').Options} [opts]
 * @returns {string}
 */ function serialize(cmpts, opts) {
    const component = {
        host: cmpts.host,
        scheme: cmpts.scheme,
        userinfo: cmpts.userinfo,
        port: cmpts.port,
        path: cmpts.path,
        query: cmpts.query,
        nid: cmpts.nid,
        nss: cmpts.nss,
        uuid: cmpts.uuid,
        fragment: cmpts.fragment,
        reference: cmpts.reference,
        resourceName: cmpts.resourceName,
        secure: cmpts.secure,
        error: ''
    };
    const options = Object.assign({}, opts);
    const uriTokens = [];
    // find scheme handler
    const schemeHandler = getSchemeHandler(options.scheme || component.scheme);
    // perform scheme specific serialization
    if (schemeHandler && schemeHandler.serialize) schemeHandler.serialize(component, options);
    if (component.path !== undefined) {
        if (!options.skipEscape) {
            component.path = escapePreservingEscapes(component.path);
            if (component.scheme !== undefined) {
                component.path = component.path.split('%3A').join(':');
            }
        } else {
            component.path = normalizePercentEncoding(component.path);
        }
    }
    if (options.reference !== 'suffix' && component.scheme) {
        uriTokens.push(component.scheme, ':');
    }
    const authority = recomposeAuthority(component);
    if (authority !== undefined) {
        if (options.reference !== 'suffix') {
            uriTokens.push('//');
        }
        uriTokens.push(authority);
        if (component.path && component.path[0] !== '/') {
            uriTokens.push('/');
        }
    }
    if (component.path !== undefined) {
        let s = component.path;
        if (!options.absolutePath && (!schemeHandler || !schemeHandler.absolutePath)) {
            s = removeDotSegments(s);
        }
        if (authority === undefined && s[0] === '/' && s[1] === '/') {
            // don't allow the path to start with "//"
            s = '/%2F' + s.slice(2);
        }
        uriTokens.push(s);
    }
    if (component.query !== undefined) {
        uriTokens.push('?', component.query);
    }
    if (component.fragment !== undefined) {
        uriTokens.push('#', component.fragment);
    }
    return uriTokens.join('');
}
const URI_PARSE = /^(?:([^#/:?]+):)?(?:\/\/((?:([^#/?@]*)@)?(\[[^#/?\]]+\]|[^#/:?]*)(?::(\d*))?))?([^#?]*)(?:\?([^#]*))?(?:#((?:.|[\n\r])*))?/u;
// Captures the authority component (between "//" and the next "/", "?" or "#"),
// with or without a scheme prefix, for the literal-backslash rejection below.
const AUTHORITY_PREFIX = /^(?:[^#/:?]+:)?\/\/([^/?#]*)/;
// Captures the leading authority-introducer region after an optional scheme: a
// run of forward slashes, backslashes, and the characters the WHATWG URL parser
// removes before parsing (TAB U+0009, LF U+000A, CR U+000D). A valid introducer
// is exactly "//". Node treats "\" as "/" on special schemes and strips those
// characters first, so forms like "\\", "/\", "\/", "/<TAB>/", or a leading
// "<TAB>//" reach an authority in Node while fast-uri's URI_PARSE folds them into
// the path group (host confusion / SSRF / redirect bypass).
const AUTHORITY_INTRODUCER_REGION = /^(?:[^#/:?]+:)?([/\\\t\n\r]*)/;
/**
 * @param {import('./types/index').URIComponent} parsed
 * @param {RegExpMatchArray} matches
 * @returns {string|undefined}
 */ function getParseError(parsed, matches) {
    if (matches[2] !== undefined && parsed.path && parsed.path[0] !== '/') {
        return 'URI path must start with "/" when authority is present.';
    }
    if (typeof parsed.port === 'number' && (parsed.port < 0 || parsed.port > 65535)) {
        return 'URI port is malformed.';
    }
    return undefined;
}
/**
 * @param {string} uri
 * @param {import('./types/index').Options} [opts]
 * @returns {{ parsed: import('./types/index').URIComponent, malformedAuthorityOrPort: boolean }}
 */ function parseWithStatus(uri, opts) {
    const options = Object.assign({}, opts);
    /** @type {import('./types/index').URIComponent} */ const parsed = {
        scheme: undefined,
        userinfo: undefined,
        host: '',
        port: undefined,
        path: '',
        query: undefined,
        fragment: undefined
    };
    let malformedAuthorityOrPort = false;
    let isIP = false;
    if (options.reference === 'suffix') {
        if (options.scheme) {
            uri = options.scheme + ':' + uri;
        } else {
            uri = '//' + uri;
        }
    }
    // A literal backslash (U+005C) is not a valid RFC 3986 URI character and is
    // not an authority delimiter. Reject it in the authority rather than
    // rewriting it: normalizing "\" -> "/" (WHATWG error recovery) could silently
    // change the resource identified by an otherwise-invalid input, and lets "\"
    // act as a host delimiter here while Node's native URL parses a different
    // host (SSRF / redirect / origin-allowlist bypass). Percent-encoded %5C is
    // untouched and remains valid encoded data.
    const authorityMatch = uri.match(AUTHORITY_PREFIX);
    if (authorityMatch !== null && authorityMatch[1].indexOf('\\') !== -1) {
        parsed.error = 'URI authority must not contain a literal backslash.';
        malformedAuthorityOrPort = true;
    }
    // Reject a malformed or whitespace-smuggled authority introducer. fast-uri
    // only recognizes a literal "//"; anything else in the leading separator run
    // (a backslash, or a "//" that appears only after removing the TAB/LF/CR that
    // Node strips) means the authority fast-uri parses differs from the one Node's
    // URL resolves. Reject rather than rewrite, mirroring the literal-backslash
    // guard above. Percent-encoded forms (%5C, %09) are untouched, valid data.
    const introducerMatch = uri.match(AUTHORITY_INTRODUCER_REGION);
    if (introducerMatch !== null) {
        const region = introducerMatch[1];
        const normalizedRegion = region.replace(/[\t\n\r]/g, '');
        // Two or more leading separators introduce an authority.
        if (normalizedRegion.length >= 2) {
            if (normalizedRegion.slice(0, 2) !== '//') {
                parsed.error = parsed.error || 'URI authority must not contain a literal backslash.';
                malformedAuthorityOrPort = true;
            } else if (region.length !== normalizedRegion.length) {
                parsed.error = parsed.error || 'URI authority introducer must not contain whitespace.';
                malformedAuthorityOrPort = true;
            }
        }
    }
    const matches = uri.match(URI_PARSE);
    if (matches) {
        // store each component
        parsed.scheme = matches[1];
        parsed.userinfo = matches[3];
        parsed.host = matches[4];
        parsed.port = parseInt(matches[5], 10);
        parsed.path = matches[6] || '';
        parsed.query = matches[7];
        parsed.fragment = matches[8];
        // fix port number
        if (isNaN(parsed.port)) {
            parsed.port = matches[5];
        }
        const parseError = getParseError(parsed, matches);
        if (parseError !== undefined) {
            parsed.error = parsed.error || parseError;
            malformedAuthorityOrPort = true;
        }
        if (parsed.host) {
            const ipv4result = isIPv4(parsed.host);
            if (ipv4result === false) {
                const ipv6result = normalizeIPv6(parsed.host);
                parsed.host = ipv6result.host.toLowerCase();
                isIP = ipv6result.isIPV6;
            } else {
                isIP = true;
            }
        }
        if (parsed.scheme === undefined && parsed.userinfo === undefined && parsed.host === undefined && parsed.port === undefined && parsed.query === undefined && !parsed.path) {
            parsed.reference = 'same-document';
        } else if (parsed.scheme === undefined) {
            parsed.reference = 'relative';
        } else if (parsed.fragment === undefined) {
            parsed.reference = 'absolute';
        } else {
            parsed.reference = 'uri';
        }
        // check for reference errors
        if (options.reference && options.reference !== 'suffix' && options.reference !== parsed.reference) {
            parsed.error = parsed.error || 'URI is not a ' + options.reference + ' reference.';
        }
        // find scheme handler
        const schemeHandler = getSchemeHandler(options.scheme || parsed.scheme);
        // check if scheme can't handle IRIs
        if (!options.unicodeSupport && (!schemeHandler || !schemeHandler.unicodeSupport)) {
            // if host component is a domain name
            if (parsed.host && (options.domainHost || schemeHandler && schemeHandler.domainHost) && isIP === false && nonSimpleDomain(parsed.host)) {
                // convert Unicode IDN -> ASCII IDN
                try {
                    parsed.host = new URL('http://' + parsed.host).hostname;
                } catch (e) {
                    parsed.error = parsed.error || "Host's domain name can not be converted to ASCII: " + e;
                }
            }
        // convert IRI -> URI
        }
        if (!schemeHandler || schemeHandler && !schemeHandler.skipNormalize) {
            if (uri.indexOf('%') !== -1) {
                if (parsed.scheme !== undefined) {
                    parsed.scheme = unescape(parsed.scheme);
                }
                if (parsed.host !== undefined) {
                    parsed.host = reescapeHostDelimiters(unescape(parsed.host), isIP);
                }
            }
            if (parsed.path) {
                parsed.path = normalizePathEncoding(parsed.path);
            }
            if (parsed.fragment) {
                try {
                    parsed.fragment = encodeURI(decodeURIComponent(parsed.fragment));
                } catch  {
                    parsed.error = parsed.error || 'URI malformed';
                }
            }
        }
        // perform scheme specific parsing
        if (schemeHandler && schemeHandler.parse) {
            schemeHandler.parse(parsed, options);
        }
    } else {
        parsed.error = parsed.error || 'URI can not be parsed.';
    }
    return {
        parsed,
        malformedAuthorityOrPort
    };
}
/**
 * @param {string} uri
 * @param {import('./types/index').Options} [opts]
 * @returns
 */ function parse(uri, opts) {
    return parseWithStatus(uri, opts).parsed;
}
/**
 * @param {string} uri
 * @param {import('./types/index').Options} [opts]
 * @returns {string}
 */ function normalizeString(uri, opts) {
    return normalizeStringWithStatus(uri, opts).normalized;
}
/**
 * @param {string} uri
 * @param {import('./types/index').Options} [opts]
 * @returns {{ normalized: string, malformedAuthorityOrPort: boolean }}
 */ function normalizeStringWithStatus(uri, opts) {
    const { parsed, malformedAuthorityOrPort } = parseWithStatus(uri, opts);
    return {
        normalized: malformedAuthorityOrPort ? uri : serialize(parsed, opts),
        malformedAuthorityOrPort
    };
}
/**
 * @param {import ('./types/index').URIComponent|string} uri
 * @param {import('./types/index').Options} [opts]
 * @returns {string|undefined}
 */ function normalizeComparableURI(uri, opts) {
    if (typeof uri === 'string') {
        const { normalized, malformedAuthorityOrPort } = normalizeStringWithStatus(uri, opts);
        return malformedAuthorityOrPort ? undefined : normalized;
    }
    if (typeof uri === 'object') {
        return serialize(uri, opts);
    }
}
const fastUri = {
    SCHEMES,
    normalize,
    resolve,
    resolveComponent,
    equal,
    serialize,
    parse
};
module.exports = fastUri;
module.exports.default = fastUri;
module.exports.fastUri = fastUri;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/lib/schemes.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

const { isUUID } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/lib/utils.js [app-client] (ecmascript)");
const URN_REG = /([\da-z][\d\-a-z]{0,31}):((?:[\w!$'()*+,\-.:;=@]|%[\da-f]{2})+)/iu;
const supportedSchemeNames = [
    'http',
    'https',
    'ws',
    'wss',
    'urn',
    'urn:uuid'
];
/** @typedef {supportedSchemeNames[number]} SchemeName */ /**
 * @param {string} name
 * @returns {name is SchemeName}
 */ function isValidSchemeName(name) {
    return supportedSchemeNames.indexOf(name) !== -1;
}
/**
 * @callback SchemeFn
 * @param {import('../types/index').URIComponent} component
 * @param {import('../types/index').Options} options
 * @returns {import('../types/index').URIComponent}
 */ /**
 * @typedef {Object} SchemeHandler
 * @property {SchemeName} scheme - The scheme name.
 * @property {boolean} [domainHost] - Indicates if the scheme supports domain hosts.
 * @property {SchemeFn} parse - Function to parse the URI component for this scheme.
 * @property {SchemeFn} serialize - Function to serialize the URI component for this scheme.
 * @property {boolean} [skipNormalize] - Indicates if normalization should be skipped for this scheme.
 * @property {boolean} [absolutePath] - Indicates if the scheme uses absolute paths.
 * @property {boolean} [unicodeSupport] - Indicates if the scheme supports Unicode.
 */ /**
 * @param {import('../types/index').URIComponent} wsComponent
 * @returns {boolean}
 */ function wsIsSecure(wsComponent) {
    if (wsComponent.secure === true) {
        return true;
    } else if (wsComponent.secure === false) {
        return false;
    } else if (wsComponent.scheme) {
        return wsComponent.scheme.length === 3 && (wsComponent.scheme[0] === 'w' || wsComponent.scheme[0] === 'W') && (wsComponent.scheme[1] === 's' || wsComponent.scheme[1] === 'S') && (wsComponent.scheme[2] === 's' || wsComponent.scheme[2] === 'S');
    } else {
        return false;
    }
}
/** @type {SchemeFn} */ function httpParse(component) {
    if (!component.host) {
        component.error = component.error || 'HTTP URIs must have a host.';
    }
    return component;
}
/** @type {SchemeFn} */ function httpSerialize(component) {
    const secure = String(component.scheme).toLowerCase() === 'https';
    // normalize the default port
    if (component.port === (secure ? 443 : 80) || component.port === '') {
        component.port = undefined;
    }
    // normalize the empty path
    if (!component.path) {
        component.path = '/';
    }
    // NOTE: We do not parse query strings for HTTP URIs
    // as WWW Form Url Encoded query strings are part of the HTML4+ spec,
    // and not the HTTP spec.
    return component;
}
/** @type {SchemeFn} */ function wsParse(wsComponent) {
    // indicate if the secure flag is set
    wsComponent.secure = wsIsSecure(wsComponent);
    // construct resouce name
    wsComponent.resourceName = (wsComponent.path || '/') + (wsComponent.query ? '?' + wsComponent.query : '');
    wsComponent.path = undefined;
    wsComponent.query = undefined;
    return wsComponent;
}
/** @type {SchemeFn} */ function wsSerialize(wsComponent) {
    // normalize the default port
    if (wsComponent.port === (wsIsSecure(wsComponent) ? 443 : 80) || wsComponent.port === '') {
        wsComponent.port = undefined;
    }
    // ensure scheme matches secure flag
    if (typeof wsComponent.secure === 'boolean') {
        wsComponent.scheme = wsComponent.secure ? 'wss' : 'ws';
        wsComponent.secure = undefined;
    }
    // reconstruct path from resource name
    if (wsComponent.resourceName) {
        const [path, query] = wsComponent.resourceName.split('?');
        wsComponent.path = path && path !== '/' ? path : undefined;
        wsComponent.query = query;
        wsComponent.resourceName = undefined;
    }
    // forbid fragment component
    wsComponent.fragment = undefined;
    return wsComponent;
}
/** @type {SchemeFn} */ function urnParse(urnComponent, options) {
    if (!urnComponent.path) {
        urnComponent.error = 'URN can not be parsed';
        return urnComponent;
    }
    const matches = urnComponent.path.match(URN_REG);
    if (matches) {
        const scheme = options.scheme || urnComponent.scheme || 'urn';
        urnComponent.nid = matches[1].toLowerCase();
        urnComponent.nss = matches[2];
        const urnScheme = `${scheme}:${options.nid || urnComponent.nid}`;
        const schemeHandler = getSchemeHandler(urnScheme);
        urnComponent.path = undefined;
        if (schemeHandler) {
            urnComponent = schemeHandler.parse(urnComponent, options);
        }
    } else {
        urnComponent.error = urnComponent.error || 'URN can not be parsed.';
    }
    return urnComponent;
}
/** @type {SchemeFn} */ function urnSerialize(urnComponent, options) {
    if (urnComponent.nid === undefined) {
        throw new Error('URN without nid cannot be serialized');
    }
    const scheme = options.scheme || urnComponent.scheme || 'urn';
    const nid = urnComponent.nid.toLowerCase();
    const urnScheme = `${scheme}:${options.nid || nid}`;
    const schemeHandler = getSchemeHandler(urnScheme);
    if (schemeHandler) {
        urnComponent = schemeHandler.serialize(urnComponent, options);
    }
    const uriComponent = urnComponent;
    const nss = urnComponent.nss;
    uriComponent.path = `${nid || options.nid}:${nss}`;
    options.skipEscape = true;
    return uriComponent;
}
/** @type {SchemeFn} */ function urnuuidParse(urnComponent, options) {
    const uuidComponent = urnComponent;
    uuidComponent.uuid = uuidComponent.nss;
    uuidComponent.nss = undefined;
    if (!options.tolerant && (!uuidComponent.uuid || !isUUID(uuidComponent.uuid))) {
        uuidComponent.error = uuidComponent.error || 'UUID is not valid.';
    }
    return uuidComponent;
}
/** @type {SchemeFn} */ function urnuuidSerialize(uuidComponent) {
    const urnComponent = uuidComponent;
    // normalize UUID
    urnComponent.nss = (uuidComponent.uuid || '').toLowerCase();
    return urnComponent;
}
const http = {
    scheme: 'http',
    domainHost: true,
    parse: httpParse,
    serialize: httpSerialize
};
const https = {
    scheme: 'https',
    domainHost: http.domainHost,
    parse: httpParse,
    serialize: httpSerialize
};
const ws = {
    scheme: 'ws',
    domainHost: true,
    parse: wsParse,
    serialize: wsSerialize
};
const wss = {
    scheme: 'wss',
    domainHost: ws.domainHost,
    parse: ws.parse,
    serialize: ws.serialize
};
const urn = {
    scheme: 'urn',
    parse: urnParse,
    serialize: urnSerialize,
    skipNormalize: true
};
const urnuuid = {
    scheme: 'urn:uuid',
    parse: urnuuidParse,
    serialize: urnuuidSerialize,
    skipNormalize: true
};
const SCHEMES = {
    http,
    https,
    ws,
    wss,
    urn,
    'urn:uuid': urnuuid
};
Object.setPrototypeOf(SCHEMES, null);
/**
 * @param {string|undefined} scheme
 * @returns {SchemeHandler|undefined}
 */ function getSchemeHandler(scheme) {
    return scheme && (SCHEMES[scheme] || SCHEMES[scheme.toLowerCase()]) || undefined;
}
module.exports = {
    wsIsSecure,
    SCHEMES,
    isValidSchemeName,
    getSchemeHandler
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/fast-uri/lib/utils.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

/** @type {(value: string) => boolean} */ const isUUID = RegExp.prototype.test.bind(/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/iu);
/** @type {(value: string) => boolean} */ const isIPv4 = RegExp.prototype.test.bind(/^(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)$/u);
/** @type {(value: string) => boolean} */ const isHexPair = RegExp.prototype.test.bind(/^[\da-f]{2}$/iu);
/** @type {(value: string) => boolean} */ const isUnreserved = RegExp.prototype.test.bind(/^[\da-z\-._~]$/iu);
/** @type {(value: string) => boolean} */ const isPathCharacter = RegExp.prototype.test.bind(/^[\da-z\-._~!$&'()*+,;=:@/]$/iu);
/**
 * @param {Array<string>} input
 * @returns {string}
 */ function stringArrayToHexStripped(input) {
    let acc = '';
    let code = 0;
    let i = 0;
    for(i = 0; i < input.length; i++){
        code = input[i].charCodeAt(0);
        if (code === 48) {
            continue;
        }
        if (!(code >= 48 && code <= 57 || code >= 65 && code <= 70 || code >= 97 && code <= 102)) {
            return '';
        }
        acc += input[i];
        break;
    }
    for(i += 1; i < input.length; i++){
        code = input[i].charCodeAt(0);
        if (!(code >= 48 && code <= 57 || code >= 65 && code <= 70 || code >= 97 && code <= 102)) {
            return '';
        }
        acc += input[i];
    }
    return acc;
}
/**
 * @typedef {Object} GetIPV6Result
 * @property {boolean} error - Indicates if there was an error parsing the IPv6 address.
 * @property {string} address - The parsed IPv6 address.
 * @property {string} [zone] - The zone identifier, if present.
 */ /**
 * @param {string} value
 * @returns {boolean}
 */ const nonSimpleDomain = RegExp.prototype.test.bind(/[^!"$&'()*+,\-.;=_`a-z{}~]/u);
/**
 * @param {Array<string>} buffer
 * @returns {boolean}
 */ function consumeIsZone(buffer) {
    buffer.length = 0;
    return true;
}
/**
 * @param {Array<string>} buffer
 * @param {Array<string>} address
 * @param {GetIPV6Result} output
 * @returns {boolean}
 */ function consumeHextets(buffer, address, output) {
    if (buffer.length) {
        const hex = stringArrayToHexStripped(buffer);
        if (hex !== '') {
            address.push(hex);
        } else {
            output.error = true;
            return false;
        }
        buffer.length = 0;
    }
    return true;
}
/**
 * @param {string} input
 * @returns {GetIPV6Result}
 */ function getIPV6(input) {
    let tokenCount = 0;
    const output = {
        error: false,
        address: '',
        zone: ''
    };
    /** @type {Array<string>} */ const address = [];
    /** @type {Array<string>} */ const buffer = [];
    let endipv6Encountered = false;
    let endIpv6 = false;
    let consume = consumeHextets;
    for(let i = 0; i < input.length; i++){
        const cursor = input[i];
        if (cursor === '[' || cursor === ']') {
            continue;
        }
        if (cursor === ':') {
            if (endipv6Encountered === true) {
                endIpv6 = true;
            }
            if (!consume(buffer, address, output)) {
                break;
            }
            if (++tokenCount > 7) {
                // not valid
                output.error = true;
                break;
            }
            if (i > 0 && input[i - 1] === ':') {
                endipv6Encountered = true;
            }
            address.push(':');
            continue;
        } else if (cursor === '%') {
            if (!consume(buffer, address, output)) {
                break;
            }
            // switch to zone detection
            consume = consumeIsZone;
        } else {
            buffer.push(cursor);
            continue;
        }
    }
    if (buffer.length) {
        if (consume === consumeIsZone) {
            output.zone = buffer.join('');
        } else if (endIpv6) {
            address.push(buffer.join(''));
        } else {
            address.push(stringArrayToHexStripped(buffer));
        }
    }
    output.address = address.join('');
    return output;
}
/**
 * @typedef {Object} NormalizeIPv6Result
 * @property {string} host - The normalized host.
 * @property {string} [escapedHost] - The escaped host.
 * @property {boolean} isIPV6 - Indicates if the host is an IPv6 address.
 */ /**
 * @param {string} host
 * @returns {NormalizeIPv6Result}
 */ function normalizeIPv6(host) {
    if (findToken(host, ':') < 2) {
        return {
            host,
            isIPV6: false
        };
    }
    const ipv6 = getIPV6(host);
    if (!ipv6.error) {
        let newHost = ipv6.address;
        let escapedHost = ipv6.address;
        if (ipv6.zone) {
            newHost += '%' + ipv6.zone;
            escapedHost += '%25' + ipv6.zone;
        }
        return {
            host: newHost,
            isIPV6: true,
            escapedHost
        };
    } else {
        return {
            host,
            isIPV6: false
        };
    }
}
/**
 * @param {string} str
 * @param {string} token
 * @returns {number}
 */ function findToken(str, token) {
    let ind = 0;
    for(let i = 0; i < str.length; i++){
        if (str[i] === token) ind++;
    }
    return ind;
}
/**
 * @param {string} path
 * @returns {string}
 *
 * @see https://datatracker.ietf.org/doc/html/rfc3986#section-5.2.4
 */ function removeDotSegments(path) {
    let input = path;
    const output = [];
    let nextSlash = -1;
    let len = 0;
    // eslint-disable-next-line no-cond-assign
    while(len = input.length){
        if (len === 1) {
            if (input === '.') {
                break;
            } else if (input === '/') {
                output.push('/');
                break;
            } else {
                output.push(input);
                break;
            }
        } else if (len === 2) {
            if (input[0] === '.') {
                if (input[1] === '.') {
                    break;
                } else if (input[1] === '/') {
                    input = input.slice(2);
                    continue;
                }
            } else if (input[0] === '/') {
                if (input[1] === '.' || input[1] === '/') {
                    output.push('/');
                    break;
                }
            }
        } else if (len === 3) {
            if (input === '/..') {
                if (output.length !== 0) {
                    output.pop();
                }
                output.push('/');
                break;
            }
        }
        if (input[0] === '.') {
            if (input[1] === '.') {
                if (input[2] === '/') {
                    input = input.slice(3);
                    continue;
                }
            } else if (input[1] === '/') {
                input = input.slice(2);
                continue;
            }
        } else if (input[0] === '/') {
            if (input[1] === '.') {
                if (input[2] === '/') {
                    input = input.slice(2);
                    continue;
                } else if (input[2] === '.') {
                    if (input[3] === '/') {
                        input = input.slice(3);
                        if (output.length !== 0) {
                            output.pop();
                        }
                        continue;
                    }
                }
            }
        }
        // Rule 2E: Move normal path segment to output
        if ((nextSlash = input.indexOf('/', 1)) === -1) {
            output.push(input);
            break;
        } else {
            output.push(input.slice(0, nextSlash));
            input = input.slice(nextSlash);
        }
    }
    return output.join('');
}
/**
 * Re-escape RFC 3986 gen-delims that must not appear literally in the host.
 * After the URI regex parses, these characters cannot be literal in the host
 * field, so any that appear after decoding came from percent-encoding and
 * must be restored to prevent authority structure changes.
 *
 * @param {string} host
 * @param {boolean} isIP - true for IPv4/IPv6 hosts (skip colon re-escaping)
 * @returns {string}
 */ const HOST_DELIMS = {
    '@': '%40',
    '/': '%2F',
    '?': '%3F',
    '#': '%23',
    ':': '%3A'
};
const HOST_DELIM_RE = /[@/?#:]/g;
const HOST_DELIM_NO_COLON_RE = /[@/?#]/g;
function reescapeHostDelimiters(host, isIP) {
    const re = isIP ? HOST_DELIM_NO_COLON_RE : HOST_DELIM_RE;
    re.lastIndex = 0;
    return host.replace(re, (ch)=>HOST_DELIMS[ch]);
}
/**
 * Normalizes percent escapes and optionally decodes only unreserved ASCII bytes.
 * Reserved delimiters such as `%2F` and `%2E` stay escaped.
 *
 * @param {string} input
 * @param {boolean} [decodeUnreserved=false]
 * @returns {string}
 */ function normalizePercentEncoding(input, decodeUnreserved = false) {
    if (input.indexOf('%') === -1) {
        return input;
    }
    let output = '';
    for(let i = 0; i < input.length; i++){
        if (input[i] === '%' && i + 2 < input.length) {
            const hex = input.slice(i + 1, i + 3);
            if (isHexPair(hex)) {
                const normalizedHex = hex.toUpperCase();
                const decoded = String.fromCharCode(parseInt(normalizedHex, 16));
                if (decodeUnreserved && isUnreserved(decoded)) {
                    output += decoded;
                } else {
                    output += '%' + normalizedHex;
                }
                i += 2;
                continue;
            }
        }
        output += input[i];
    }
    return output;
}
/**
 * Normalizes path data without turning reserved escapes into live path syntax.
 * Valid escapes are uppercased, raw unsafe characters are escaped, and only
 * unreserved bytes that are not `.` are decoded.
 *
 * @param {string} input
 * @returns {string}
 */ function normalizePathEncoding(input) {
    let output = '';
    for(let i = 0; i < input.length; i++){
        if (input[i] === '%' && i + 2 < input.length) {
            const hex = input.slice(i + 1, i + 3);
            if (isHexPair(hex)) {
                const normalizedHex = hex.toUpperCase();
                const decoded = String.fromCharCode(parseInt(normalizedHex, 16));
                if (decoded !== '.' && isUnreserved(decoded)) {
                    output += decoded;
                } else {
                    output += '%' + normalizedHex;
                }
                i += 2;
                continue;
            }
        }
        if (isPathCharacter(input[i])) {
            output += input[i];
        } else {
            output += escape(input[i]);
        }
    }
    return output;
}
/**
 * Escapes a component while preserving existing valid percent escapes.
 *
 * @param {string} input
 * @returns {string}
 */ function escapePreservingEscapes(input) {
    let output = '';
    for(let i = 0; i < input.length; i++){
        if (input[i] === '%' && i + 2 < input.length) {
            const hex = input.slice(i + 1, i + 3);
            if (isHexPair(hex)) {
                output += '%' + hex.toUpperCase();
                i += 2;
                continue;
            }
        }
        output += escape(input[i]);
    }
    return output;
}
/**
 * @param {import('../types/index').URIComponent} component
 * @returns {string|undefined}
 */ function recomposeAuthority(component) {
    const uriTokens = [];
    if (component.userinfo !== undefined) {
        uriTokens.push(component.userinfo);
        uriTokens.push('@');
    }
    if (component.host !== undefined) {
        let host = unescape(component.host);
        if (!isIPv4(host)) {
            const ipV6res = normalizeIPv6(host);
            if (ipV6res.isIPV6 === true) {
                host = `[${ipV6res.escapedHost}]`;
            } else {
                host = reescapeHostDelimiters(host, false);
            }
        }
        uriTokens.push(host);
    }
    if (typeof component.port === 'number' || typeof component.port === 'string') {
        uriTokens.push(':');
        uriTokens.push(String(component.port));
    }
    return uriTokens.length ? uriTokens.join('') : undefined;
}
;
module.exports = {
    nonSimpleDomain,
    recomposeAuthority,
    reescapeHostDelimiters,
    normalizePercentEncoding,
    normalizePathEncoding,
    escapePreservingEscapes,
    removeDotSegments,
    isIPv4,
    isUUID,
    normalizeIPv6,
    stringArrayToHexStripped
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/focus-trap/dist/focus-trap.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "createFocusTrap",
    ()=>createFocusTrap
]);
/*!
* focus-trap 7.5.4
* @license MIT, https://github.com/focus-trap/focus-trap/blob/master/LICENSE
*/ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/tabbable/dist/index.esm.js [app-client] (ecmascript)");
;
function ownKeys(e, r) {
    var t = Object.keys(e);
    if (Object.getOwnPropertySymbols) {
        var o = Object.getOwnPropertySymbols(e);
        r && (o = o.filter(function(r) {
            return Object.getOwnPropertyDescriptor(e, r).enumerable;
        })), t.push.apply(t, o);
    }
    return t;
}
function _objectSpread2(e) {
    for(var r = 1; r < arguments.length; r++){
        var t = null != arguments[r] ? arguments[r] : {};
        r % 2 ? ownKeys(Object(t), !0).forEach(function(r) {
            _defineProperty(e, r, t[r]);
        }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function(r) {
            Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r));
        });
    }
    return e;
}
function _defineProperty(obj, key, value) {
    key = _toPropertyKey(key);
    if (key in obj) {
        Object.defineProperty(obj, key, {
            value: value,
            enumerable: true,
            configurable: true,
            writable: true
        });
    } else {
        obj[key] = value;
    }
    return obj;
}
function _toPrimitive(input, hint) {
    if (typeof input !== "object" || input === null) return input;
    var prim = input[Symbol.toPrimitive];
    if (prim !== undefined) {
        var res = prim.call(input, hint || "default");
        if (typeof res !== "object") return res;
        throw new TypeError("@@toPrimitive must return a primitive value.");
    }
    return (hint === "string" ? String : Number)(input);
}
function _toPropertyKey(arg) {
    var key = _toPrimitive(arg, "string");
    return typeof key === "symbol" ? key : String(key);
}
var activeFocusTraps = {
    activateTrap: function activateTrap(trapStack, trap) {
        if (trapStack.length > 0) {
            var activeTrap = trapStack[trapStack.length - 1];
            if (activeTrap !== trap) {
                activeTrap.pause();
            }
        }
        var trapIndex = trapStack.indexOf(trap);
        if (trapIndex === -1) {
            trapStack.push(trap);
        } else {
            // move this existing trap to the front of the queue
            trapStack.splice(trapIndex, 1);
            trapStack.push(trap);
        }
    },
    deactivateTrap: function deactivateTrap(trapStack, trap) {
        var trapIndex = trapStack.indexOf(trap);
        if (trapIndex !== -1) {
            trapStack.splice(trapIndex, 1);
        }
        if (trapStack.length > 0) {
            trapStack[trapStack.length - 1].unpause();
        }
    }
};
var isSelectableInput = function isSelectableInput(node) {
    return node.tagName && node.tagName.toLowerCase() === 'input' && typeof node.select === 'function';
};
var isEscapeEvent = function isEscapeEvent(e) {
    return (e === null || e === void 0 ? void 0 : e.key) === 'Escape' || (e === null || e === void 0 ? void 0 : e.key) === 'Esc' || (e === null || e === void 0 ? void 0 : e.keyCode) === 27;
};
var isTabEvent = function isTabEvent(e) {
    return (e === null || e === void 0 ? void 0 : e.key) === 'Tab' || (e === null || e === void 0 ? void 0 : e.keyCode) === 9;
};
// checks for TAB by default
var isKeyForward = function isKeyForward(e) {
    return isTabEvent(e) && !e.shiftKey;
};
// checks for SHIFT+TAB by default
var isKeyBackward = function isKeyBackward(e) {
    return isTabEvent(e) && e.shiftKey;
};
var delay = function delay(fn) {
    return setTimeout(fn, 0);
};
// Array.find/findIndex() are not supported on IE; this replicates enough
//  of Array.findIndex() for our needs
var findIndex = function findIndex(arr, fn) {
    var idx = -1;
    arr.every(function(value, i) {
        if (fn(value)) {
            idx = i;
            return false; // break
        }
        return true; // next
    });
    return idx;
};
/**
 * Get an option's value when it could be a plain value, or a handler that provides
 *  the value.
 * @param {*} value Option's value to check.
 * @param {...*} [params] Any parameters to pass to the handler, if `value` is a function.
 * @returns {*} The `value`, or the handler's returned value.
 */ var valueOrHandler = function valueOrHandler(value) {
    for(var _len = arguments.length, params = new Array(_len > 1 ? _len - 1 : 0), _key = 1; _key < _len; _key++){
        params[_key - 1] = arguments[_key];
    }
    return typeof value === 'function' ? value.apply(void 0, params) : value;
};
var getActualTarget = function getActualTarget(event) {
    // NOTE: If the trap is _inside_ a shadow DOM, event.target will always be the
    //  shadow host. However, event.target.composedPath() will be an array of
    //  nodes "clicked" from inner-most (the actual element inside the shadow) to
    //  outer-most (the host HTML document). If we have access to composedPath(),
    //  then use its first element; otherwise, fall back to event.target (and
    //  this only works for an _open_ shadow DOM; otherwise,
    //  composedPath()[0] === event.target always).
    return event.target.shadowRoot && typeof event.composedPath === 'function' ? event.composedPath()[0] : event.target;
};
// NOTE: this must be _outside_ `createFocusTrap()` to make sure all traps in this
//  current instance use the same stack if `userOptions.trapStack` isn't specified
var internalTrapStack = [];
var createFocusTrap = function createFocusTrap(elements, userOptions) {
    // SSR: a live trap shouldn't be created in this type of environment so this
    //  should be safe code to execute if the `document` option isn't specified
    var doc = (userOptions === null || userOptions === void 0 ? void 0 : userOptions.document) || document;
    var trapStack = (userOptions === null || userOptions === void 0 ? void 0 : userOptions.trapStack) || internalTrapStack;
    var config = _objectSpread2({
        returnFocusOnDeactivate: true,
        escapeDeactivates: true,
        delayInitialFocus: true,
        isKeyForward: isKeyForward,
        isKeyBackward: isKeyBackward
    }, userOptions);
    var state = {
        // containers given to createFocusTrap()
        // @type {Array<HTMLElement>}
        containers: [],
        // list of objects identifying tabbable nodes in `containers` in the trap
        // NOTE: it's possible that a group has no tabbable nodes if nodes get removed while the trap
        //  is active, but the trap should never get to a state where there isn't at least one group
        //  with at least one tabbable node in it (that would lead to an error condition that would
        //  result in an error being thrown)
        // @type {Array<{
        //   container: HTMLElement,
        //   tabbableNodes: Array<HTMLElement>, // empty if none
        //   focusableNodes: Array<HTMLElement>, // empty if none
        //   posTabIndexesFound: boolean,
        //   firstTabbableNode: HTMLElement|undefined,
        //   lastTabbableNode: HTMLElement|undefined,
        //   firstDomTabbableNode: HTMLElement|undefined,
        //   lastDomTabbableNode: HTMLElement|undefined,
        //   nextTabbableNode: (node: HTMLElement, forward: boolean) => HTMLElement|undefined
        // }>}
        containerGroups: [],
        // same order/length as `containers` list
        // references to objects in `containerGroups`, but only those that actually have
        //  tabbable nodes in them
        // NOTE: same order as `containers` and `containerGroups`, but __not necessarily__
        //  the same length
        tabbableGroups: [],
        nodeFocusedBeforeActivation: null,
        mostRecentlyFocusedNode: null,
        active: false,
        paused: false,
        // timer ID for when delayInitialFocus is true and initial focus in this trap
        //  has been delayed during activation
        delayInitialFocusTimer: undefined,
        // the most recent KeyboardEvent for the configured nav key (typically [SHIFT+]TAB), if any
        recentNavEvent: undefined
    };
    var trap; // eslint-disable-line prefer-const -- some private functions reference it, and its methods reference private functions, so we must declare here and define later
    /**
   * Gets a configuration option value.
   * @param {Object|undefined} configOverrideOptions If true, and option is defined in this set,
   *  value will be taken from this object. Otherwise, value will be taken from base configuration.
   * @param {string} optionName Name of the option whose value is sought.
   * @param {string|undefined} [configOptionName] Name of option to use __instead of__ `optionName`
   *  IIF `configOverrideOptions` is not defined. Otherwise, `optionName` is used.
   */ var getOption = function getOption(configOverrideOptions, optionName, configOptionName) {
        return configOverrideOptions && configOverrideOptions[optionName] !== undefined ? configOverrideOptions[optionName] : config[configOptionName || optionName];
    };
    /**
   * Finds the index of the container that contains the element.
   * @param {HTMLElement} element
   * @param {Event} [event] If available, and `element` isn't directly found in any container,
   *  the event's composed path is used to see if includes any known trap containers in the
   *  case where the element is inside a Shadow DOM.
   * @returns {number} Index of the container in either `state.containers` or
   *  `state.containerGroups` (the order/length of these lists are the same); -1
   *  if the element isn't found.
   */ var findContainerIndex = function findContainerIndex(element, event) {
        var composedPath = typeof (event === null || event === void 0 ? void 0 : event.composedPath) === 'function' ? event.composedPath() : undefined;
        // NOTE: search `containerGroups` because it's possible a group contains no tabbable
        //  nodes, but still contains focusable nodes (e.g. if they all have `tabindex=-1`)
        //  and we still need to find the element in there
        return state.containerGroups.findIndex(function(_ref) {
            var container = _ref.container, tabbableNodes = _ref.tabbableNodes;
            return container.contains(element) || (//  web components if the `tabbableOptions.getShadowRoot` option was used for
            //  the trap, enabling shadow DOM support in tabbable (`Node.contains()` doesn't
            //  look inside web components even if open)
            composedPath === null || composedPath === void 0 ? void 0 : composedPath.includes(container)) || tabbableNodes.find(function(node) {
                return node === element;
            });
        });
    };
    /**
   * Gets the node for the given option, which is expected to be an option that
   *  can be either a DOM node, a string that is a selector to get a node, `false`
   *  (if a node is explicitly NOT given), or a function that returns any of these
   *  values.
   * @param {string} optionName
   * @returns {undefined | false | HTMLElement | SVGElement} Returns
   *  `undefined` if the option is not specified; `false` if the option
   *  resolved to `false` (node explicitly not given); otherwise, the resolved
   *  DOM node.
   * @throws {Error} If the option is set, not `false`, and is not, or does not
   *  resolve to a node.
   */ var getNodeForOption = function getNodeForOption(optionName) {
        var optionValue = config[optionName];
        if (typeof optionValue === 'function') {
            for(var _len2 = arguments.length, params = new Array(_len2 > 1 ? _len2 - 1 : 0), _key2 = 1; _key2 < _len2; _key2++){
                params[_key2 - 1] = arguments[_key2];
            }
            optionValue = optionValue.apply(void 0, params);
        }
        if (optionValue === true) {
            optionValue = undefined; // use default value
        }
        if (!optionValue) {
            if (optionValue === undefined || optionValue === false) {
                return optionValue;
            }
            // else, empty string (invalid), null (invalid), 0 (invalid)
            throw new Error("`".concat(optionName, "` was specified but was not a node, or did not return a node"));
        }
        var node = optionValue; // could be HTMLElement, SVGElement, or non-empty string at this point
        if (typeof optionValue === 'string') {
            node = doc.querySelector(optionValue); // resolve to node, or null if fails
            if (!node) {
                throw new Error("`".concat(optionName, "` as selector refers to no known node"));
            }
        }
        return node;
    };
    var getInitialFocusNode = function getInitialFocusNode() {
        var node = getNodeForOption('initialFocus');
        // false explicitly indicates we want no initialFocus at all
        if (node === false) {
            return false;
        }
        if (node === undefined || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isFocusable"])(node, config.tabbableOptions)) {
            // option not specified nor focusable: use fallback options
            if (findContainerIndex(doc.activeElement) >= 0) {
                node = doc.activeElement;
            } else {
                var firstTabbableGroup = state.tabbableGroups[0];
                var firstTabbableNode = firstTabbableGroup && firstTabbableGroup.firstTabbableNode;
                // NOTE: `fallbackFocus` option function cannot return `false` (not supported)
                node = firstTabbableNode || getNodeForOption('fallbackFocus');
            }
        }
        if (!node) {
            throw new Error('Your focus-trap needs to have at least one focusable element');
        }
        return node;
    };
    var updateTabbableNodes = function updateTabbableNodes() {
        state.containerGroups = state.containers.map(function(container) {
            var tabbableNodes = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["tabbable"])(container, config.tabbableOptions);
            // NOTE: if we have tabbable nodes, we must have focusable nodes; focusable nodes
            //  are a superset of tabbable nodes since nodes with negative `tabindex` attributes
            //  are focusable but not tabbable
            var focusableNodes = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["focusable"])(container, config.tabbableOptions);
            var firstTabbableNode = tabbableNodes.length > 0 ? tabbableNodes[0] : undefined;
            var lastTabbableNode = tabbableNodes.length > 0 ? tabbableNodes[tabbableNodes.length - 1] : undefined;
            var firstDomTabbableNode = focusableNodes.find(function(node) {
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(node);
            });
            var lastDomTabbableNode = focusableNodes.slice().reverse().find(function(node) {
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(node);
            });
            var posTabIndexesFound = !!tabbableNodes.find(function(node) {
                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTabIndex"])(node) > 0;
            });
            return {
                container: container,
                tabbableNodes: tabbableNodes,
                focusableNodes: focusableNodes,
                /** True if at least one node with positive `tabindex` was found in this container. */ posTabIndexesFound: posTabIndexesFound,
                /** First tabbable node in container, __tabindex__ order; `undefined` if none. */ firstTabbableNode: firstTabbableNode,
                /** Last tabbable node in container, __tabindex__ order; `undefined` if none. */ lastTabbableNode: lastTabbableNode,
                // NOTE: DOM order is NOT NECESSARILY "document position" order, but figuring that out
                //  would require more than just https://developer.mozilla.org/en-US/docs/Web/API/Node/compareDocumentPosition
                //  because that API doesn't work with Shadow DOM as well as it should (@see
                //  https://github.com/whatwg/dom/issues/320) and since this first/last is only needed, so far,
                //  to address an edge case related to positive tabindex support, this seems like a much easier,
                //  "close enough most of the time" alternative for positive tabindexes which should generally
                //  be avoided anyway...
                /** First tabbable node in container, __DOM__ order; `undefined` if none. */ firstDomTabbableNode: firstDomTabbableNode,
                /** Last tabbable node in container, __DOM__ order; `undefined` if none. */ lastDomTabbableNode: lastDomTabbableNode,
                /**
         * Finds the __tabbable__ node that follows the given node in the specified direction,
         *  in this container, if any.
         * @param {HTMLElement} node
         * @param {boolean} [forward] True if going in forward tab order; false if going
         *  in reverse.
         * @returns {HTMLElement|undefined} The next tabbable node, if any.
         */ nextTabbableNode: function nextTabbableNode(node) {
                    var forward = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : true;
                    var nodeIdx = tabbableNodes.indexOf(node);
                    if (nodeIdx < 0) {
                        // either not tabbable nor focusable, or was focused but not tabbable (negative tabindex):
                        //  since `node` should at least have been focusable, we assume that's the case and mimic
                        //  what browsers do, which is set focus to the next node in __document position order__,
                        //  regardless of positive tabindexes, if any -- and for reasons explained in the NOTE
                        //  above related to `firstDomTabbable` and `lastDomTabbable` properties, we fall back to
                        //  basic DOM order
                        if (forward) {
                            return focusableNodes.slice(focusableNodes.indexOf(node) + 1).find(function(el) {
                                return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(el);
                            });
                        }
                        return focusableNodes.slice(0, focusableNodes.indexOf(node)).reverse().find(function(el) {
                            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(el);
                        });
                    }
                    return tabbableNodes[nodeIdx + (forward ? 1 : -1)];
                }
            };
        });
        state.tabbableGroups = state.containerGroups.filter(function(group) {
            return group.tabbableNodes.length > 0;
        });
        // throw if no groups have tabbable nodes and we don't have a fallback focus node either
        if (state.tabbableGroups.length <= 0 && !getNodeForOption('fallbackFocus') // returning false not supported for this option
        ) {
            throw new Error('Your focus-trap must have at least one container with at least one tabbable node in it at all times');
        }
        // NOTE: Positive tabindexes are only properly supported in single-container traps because
        //  doing it across multiple containers where tabindexes could be all over the place
        //  would require Tabbable to support multiple containers, would require additional
        //  specialized Shadow DOM support, and would require Tabbable's multi-container support
        //  to look at those containers in document position order rather than user-provided
        //  order (as they are treated in Focus-trap, for legacy reasons). See discussion on
        //  https://github.com/focus-trap/focus-trap/issues/375 for more details.
        if (state.containerGroups.find(function(g) {
            return g.posTabIndexesFound;
        }) && state.containerGroups.length > 1) {
            throw new Error("At least one node with a positive tabindex was found in one of your focus-trap's multiple containers. Positive tabindexes are only supported in single-container focus-traps.");
        }
    };
    /**
   * Gets the current activeElement. If it's a web-component and has open shadow-root
   * it will recursively search inside shadow roots for the "true" activeElement.
   *
   * @param {Document | ShadowRoot} el
   *
   * @returns {HTMLElement} The element that currently has the focus
   **/ var getActiveElement = function getActiveElement(el) {
        var activeElement = el.activeElement;
        if (!activeElement) {
            return;
        }
        if (activeElement.shadowRoot && activeElement.shadowRoot.activeElement !== null) {
            return getActiveElement(activeElement.shadowRoot);
        }
        return activeElement;
    };
    var tryFocus = function tryFocus(node) {
        if (node === false) {
            return;
        }
        if (node === getActiveElement(document)) {
            return;
        }
        if (!node || !node.focus) {
            tryFocus(getInitialFocusNode());
            return;
        }
        node.focus({
            preventScroll: !!config.preventScroll
        });
        // NOTE: focus() API does not trigger focusIn event so set MRU node manually
        state.mostRecentlyFocusedNode = node;
        if (isSelectableInput(node)) {
            node.select();
        }
    };
    var getReturnFocusNode = function getReturnFocusNode(previousActiveElement) {
        var node = getNodeForOption('setReturnFocus', previousActiveElement);
        return node ? node : node === false ? false : previousActiveElement;
    };
    /**
   * Finds the next node (in either direction) where focus should move according to a
   *  keyboard focus-in event.
   * @param {Object} params
   * @param {Node} [params.target] Known target __from which__ to navigate, if any.
   * @param {KeyboardEvent|FocusEvent} [params.event] Event to use if `target` isn't known (event
   *  will be used to determine the `target`). Ignored if `target` is specified.
   * @param {boolean} [params.isBackward] True if focus should move backward.
   * @returns {Node|undefined} The next node, or `undefined` if a next node couldn't be
   *  determined given the current state of the trap.
   */ var findNextNavNode = function findNextNavNode(_ref2) {
        var target = _ref2.target, event = _ref2.event, _ref2$isBackward = _ref2.isBackward, isBackward = _ref2$isBackward === void 0 ? false : _ref2$isBackward;
        target = target || getActualTarget(event);
        updateTabbableNodes();
        var destinationNode = null;
        if (state.tabbableGroups.length > 0) {
            // make sure the target is actually contained in a group
            // NOTE: the target may also be the container itself if it's focusable
            //  with tabIndex='-1' and was given initial focus
            var containerIndex = findContainerIndex(target, event);
            var containerGroup = containerIndex >= 0 ? state.containerGroups[containerIndex] : undefined;
            if (containerIndex < 0) {
                // target not found in any group: quite possible focus has escaped the trap,
                //  so bring it back into...
                if (isBackward) {
                    // ...the last node in the last group
                    destinationNode = state.tabbableGroups[state.tabbableGroups.length - 1].lastTabbableNode;
                } else {
                    // ...the first node in the first group
                    destinationNode = state.tabbableGroups[0].firstTabbableNode;
                }
            } else if (isBackward) {
                // REVERSE
                // is the target the first tabbable node in a group?
                var startOfGroupIndex = findIndex(state.tabbableGroups, function(_ref3) {
                    var firstTabbableNode = _ref3.firstTabbableNode;
                    return target === firstTabbableNode;
                });
                if (startOfGroupIndex < 0 && (containerGroup.container === target || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isFocusable"])(target, config.tabbableOptions) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(target, config.tabbableOptions) && !containerGroup.nextTabbableNode(target, false))) {
                    // an exception case where the target is either the container itself, or
                    //  a non-tabbable node that was given focus (i.e. tabindex is negative
                    //  and user clicked on it or node was programmatically given focus)
                    //  and is not followed by any other tabbable node, in which
                    //  case, we should handle shift+tab as if focus were on the container's
                    //  first tabbable node, and go to the last tabbable node of the LAST group
                    startOfGroupIndex = containerIndex;
                }
                if (startOfGroupIndex >= 0) {
                    // YES: then shift+tab should go to the last tabbable node in the
                    //  previous group (and wrap around to the last tabbable node of
                    //  the LAST group if it's the first tabbable node of the FIRST group)
                    var destinationGroupIndex = startOfGroupIndex === 0 ? state.tabbableGroups.length - 1 : startOfGroupIndex - 1;
                    var destinationGroup = state.tabbableGroups[destinationGroupIndex];
                    destinationNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTabIndex"])(target) >= 0 ? destinationGroup.lastTabbableNode : destinationGroup.lastDomTabbableNode;
                } else if (!isTabEvent(event)) {
                    // user must have customized the nav keys so we have to move focus manually _within_
                    //  the active group: do this based on the order determined by tabbable()
                    destinationNode = containerGroup.nextTabbableNode(target, false);
                }
            } else {
                // FORWARD
                // is the target the last tabbable node in a group?
                var lastOfGroupIndex = findIndex(state.tabbableGroups, function(_ref4) {
                    var lastTabbableNode = _ref4.lastTabbableNode;
                    return target === lastTabbableNode;
                });
                if (lastOfGroupIndex < 0 && (containerGroup.container === target || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isFocusable"])(target, config.tabbableOptions) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isTabbable"])(target, config.tabbableOptions) && !containerGroup.nextTabbableNode(target))) {
                    // an exception case where the target is the container itself, or
                    //  a non-tabbable node that was given focus (i.e. tabindex is negative
                    //  and user clicked on it or node was programmatically given focus)
                    //  and is not followed by any other tabbable node, in which
                    //  case, we should handle tab as if focus were on the container's
                    //  last tabbable node, and go to the first tabbable node of the FIRST group
                    lastOfGroupIndex = containerIndex;
                }
                if (lastOfGroupIndex >= 0) {
                    // YES: then tab should go to the first tabbable node in the next
                    //  group (and wrap around to the first tabbable node of the FIRST
                    //  group if it's the last tabbable node of the LAST group)
                    var _destinationGroupIndex = lastOfGroupIndex === state.tabbableGroups.length - 1 ? 0 : lastOfGroupIndex + 1;
                    var _destinationGroup = state.tabbableGroups[_destinationGroupIndex];
                    destinationNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTabIndex"])(target) >= 0 ? _destinationGroup.firstTabbableNode : _destinationGroup.firstDomTabbableNode;
                } else if (!isTabEvent(event)) {
                    // user must have customized the nav keys so we have to move focus manually _within_
                    //  the active group: do this based on the order determined by tabbable()
                    destinationNode = containerGroup.nextTabbableNode(target);
                }
            }
        } else {
            // no groups available
            // NOTE: the fallbackFocus option does not support returning false to opt-out
            destinationNode = getNodeForOption('fallbackFocus');
        }
        return destinationNode;
    };
    // This needs to be done on mousedown and touchstart instead of click
    // so that it precedes the focus event.
    var checkPointerDown = function checkPointerDown(e) {
        var target = getActualTarget(e);
        if (findContainerIndex(target, e) >= 0) {
            // allow the click since it ocurred inside the trap
            return;
        }
        if (valueOrHandler(config.clickOutsideDeactivates, e)) {
            // immediately deactivate the trap
            trap.deactivate({
                // NOTE: by setting `returnFocus: false`, deactivate() will do nothing,
                //  which will result in the outside click setting focus to the node
                //  that was clicked (and if not focusable, to "nothing"); by setting
                //  `returnFocus: true`, we'll attempt to re-focus the node originally-focused
                //  on activation (or the configured `setReturnFocus` node), whether the
                //  outside click was on a focusable node or not
                returnFocus: config.returnFocusOnDeactivate
            });
            return;
        }
        // This is needed for mobile devices.
        // (If we'll only let `click` events through,
        // then on mobile they will be blocked anyways if `touchstart` is blocked.)
        if (valueOrHandler(config.allowOutsideClick, e)) {
            // allow the click outside the trap to take place
            return;
        }
        // otherwise, prevent the click
        e.preventDefault();
    };
    // In case focus escapes the trap for some strange reason, pull it back in.
    // NOTE: the focusIn event is NOT cancelable, so if focus escapes, it may cause unexpected
    //  scrolling if the node that got focused was out of view; there's nothing we can do to
    //  prevent that from happening by the time we discover that focus escaped
    var checkFocusIn = function checkFocusIn(event) {
        var target = getActualTarget(event);
        var targetContained = findContainerIndex(target, event) >= 0;
        // In Firefox when you Tab out of an iframe the Document is briefly focused.
        if (targetContained || target instanceof Document) {
            if (targetContained) {
                state.mostRecentlyFocusedNode = target;
            }
        } else {
            // escaped! pull it back in to where it just left
            event.stopImmediatePropagation();
            // focus will escape if the MRU node had a positive tab index and user tried to nav forward;
            //  it will also escape if the MRU node had a 0 tab index and user tried to nav backward
            //  toward a node with a positive tab index
            var nextNode; // next node to focus, if we find one
            var navAcrossContainers = true;
            if (state.mostRecentlyFocusedNode) {
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTabIndex"])(state.mostRecentlyFocusedNode) > 0) {
                    // MRU container index must be >=0 otherwise we wouldn't have it as an MRU node...
                    var mruContainerIdx = findContainerIndex(state.mostRecentlyFocusedNode);
                    // there MAY not be any tabbable nodes in the container if there are at least 2 containers
                    //  and the MRU node is focusable but not tabbable (focus-trap requires at least 1 container
                    //  with at least one tabbable node in order to function, so this could be the other container
                    //  with nothing tabbable in it)
                    var tabbableNodes = state.containerGroups[mruContainerIdx].tabbableNodes;
                    if (tabbableNodes.length > 0) {
                        // MRU tab index MAY not be found if the MRU node is focusable but not tabbable
                        var mruTabIdx = tabbableNodes.findIndex(function(node) {
                            return node === state.mostRecentlyFocusedNode;
                        });
                        if (mruTabIdx >= 0) {
                            if (config.isKeyForward(state.recentNavEvent)) {
                                if (mruTabIdx + 1 < tabbableNodes.length) {
                                    nextNode = tabbableNodes[mruTabIdx + 1];
                                    navAcrossContainers = false;
                                }
                            // else, don't wrap within the container as focus should move to next/previous
                            //  container
                            } else {
                                if (mruTabIdx - 1 >= 0) {
                                    nextNode = tabbableNodes[mruTabIdx - 1];
                                    navAcrossContainers = false;
                                }
                            // else, don't wrap within the container as focus should move to next/previous
                            //  container
                            }
                        // else, don't find in container order without considering direction too
                        }
                    }
                // else, no tabbable nodes in that container (which means we must have at least one other
                //  container with at least one tabbable node in it, otherwise focus-trap would've thrown
                //  an error the last time updateTabbableNodes() was run): find next node among all known
                //  containers
                } else {
                    // check to see if there's at least one tabbable node with a positive tab index inside
                    //  the trap because focus seems to escape when navigating backward from a tabbable node
                    //  with tabindex=0 when this is the case (instead of wrapping to the tabbable node with
                    //  the greatest positive tab index like it should)
                    if (!state.containerGroups.some(function(g) {
                        return g.tabbableNodes.some(function(n) {
                            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$tabbable$2f$dist$2f$index$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTabIndex"])(n) > 0;
                        });
                    })) {
                        // no containers with tabbable nodes with positive tab indexes which means the focus
                        //  escaped for some other reason and we should just execute the fallback to the
                        //  MRU node or initial focus node, if any
                        navAcrossContainers = false;
                    }
                }
            } else {
                // no MRU node means we're likely in some initial condition when the trap has just
                //  been activated and initial focus hasn't been given yet, in which case we should
                //  fall through to trying to focus the initial focus node, which is what should
                //  happen below at this point in the logic
                navAcrossContainers = false;
            }
            if (navAcrossContainers) {
                nextNode = findNextNavNode({
                    // move FROM the MRU node, not event-related node (which will be the node that is
                    //  outside the trap causing the focus escape we're trying to fix)
                    target: state.mostRecentlyFocusedNode,
                    isBackward: config.isKeyBackward(state.recentNavEvent)
                });
            }
            if (nextNode) {
                tryFocus(nextNode);
            } else {
                tryFocus(state.mostRecentlyFocusedNode || getInitialFocusNode());
            }
        }
        state.recentNavEvent = undefined; // clear
    };
    // Hijack key nav events on the first and last focusable nodes of the trap,
    // in order to prevent focus from escaping. If it escapes for even a
    // moment it can end up scrolling the page and causing confusion so we
    // kind of need to capture the action at the keydown phase.
    var checkKeyNav = function checkKeyNav(event) {
        var isBackward = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;
        state.recentNavEvent = event;
        var destinationNode = findNextNavNode({
            event: event,
            isBackward: isBackward
        });
        if (destinationNode) {
            if (isTabEvent(event)) {
                // since tab natively moves focus, we wouldn't have a destination node unless we
                //  were on the edge of a container and had to move to the next/previous edge, in
                //  which case we want to prevent default to keep the browser from moving focus
                //  to where it normally would
                event.preventDefault();
            }
            tryFocus(destinationNode);
        }
    // else, let the browser take care of [shift+]tab and move the focus
    };
    var checkKey = function checkKey(event) {
        if (isEscapeEvent(event) && valueOrHandler(config.escapeDeactivates, event) !== false) {
            event.preventDefault();
            trap.deactivate();
            return;
        }
        if (config.isKeyForward(event) || config.isKeyBackward(event)) {
            checkKeyNav(event, config.isKeyBackward(event));
        }
    };
    var checkClick = function checkClick(e) {
        var target = getActualTarget(e);
        if (findContainerIndex(target, e) >= 0) {
            return;
        }
        if (valueOrHandler(config.clickOutsideDeactivates, e)) {
            return;
        }
        if (valueOrHandler(config.allowOutsideClick, e)) {
            return;
        }
        e.preventDefault();
        e.stopImmediatePropagation();
    };
    //
    // EVENT LISTENERS
    //
    var addListeners = function addListeners() {
        if (!state.active) {
            return;
        }
        // There can be only one listening focus trap at a time
        activeFocusTraps.activateTrap(trapStack, trap);
        // Delay ensures that the focused element doesn't capture the event
        // that caused the focus trap activation.
        state.delayInitialFocusTimer = config.delayInitialFocus ? delay(function() {
            tryFocus(getInitialFocusNode());
        }) : tryFocus(getInitialFocusNode());
        doc.addEventListener('focusin', checkFocusIn, true);
        doc.addEventListener('mousedown', checkPointerDown, {
            capture: true,
            passive: false
        });
        doc.addEventListener('touchstart', checkPointerDown, {
            capture: true,
            passive: false
        });
        doc.addEventListener('click', checkClick, {
            capture: true,
            passive: false
        });
        doc.addEventListener('keydown', checkKey, {
            capture: true,
            passive: false
        });
        return trap;
    };
    var removeListeners = function removeListeners() {
        if (!state.active) {
            return;
        }
        doc.removeEventListener('focusin', checkFocusIn, true);
        doc.removeEventListener('mousedown', checkPointerDown, true);
        doc.removeEventListener('touchstart', checkPointerDown, true);
        doc.removeEventListener('click', checkClick, true);
        doc.removeEventListener('keydown', checkKey, true);
        return trap;
    };
    //
    // MUTATION OBSERVER
    //
    var checkDomRemoval = function checkDomRemoval(mutations) {
        var isFocusedNodeRemoved = mutations.some(function(mutation) {
            var removedNodes = Array.from(mutation.removedNodes);
            return removedNodes.some(function(node) {
                return node === state.mostRecentlyFocusedNode;
            });
        });
        // If the currently focused is removed then browsers will move focus to the
        // <body> element. If this happens, try to move focus back into the trap.
        if (isFocusedNodeRemoved) {
            tryFocus(getInitialFocusNode());
        }
    };
    // Use MutationObserver - if supported - to detect if focused node is removed
    // from the DOM.
    var mutationObserver = typeof window !== 'undefined' && 'MutationObserver' in window ? new MutationObserver(checkDomRemoval) : undefined;
    var updateObservedNodes = function updateObservedNodes() {
        if (!mutationObserver) {
            return;
        }
        mutationObserver.disconnect();
        if (state.active && !state.paused) {
            state.containers.map(function(container) {
                mutationObserver.observe(container, {
                    subtree: true,
                    childList: true
                });
            });
        }
    };
    //
    // TRAP DEFINITION
    //
    trap = {
        get active () {
            return state.active;
        },
        get paused () {
            return state.paused;
        },
        activate: function activate(activateOptions) {
            if (state.active) {
                return this;
            }
            var onActivate = getOption(activateOptions, 'onActivate');
            var onPostActivate = getOption(activateOptions, 'onPostActivate');
            var checkCanFocusTrap = getOption(activateOptions, 'checkCanFocusTrap');
            if (!checkCanFocusTrap) {
                updateTabbableNodes();
            }
            state.active = true;
            state.paused = false;
            state.nodeFocusedBeforeActivation = doc.activeElement;
            onActivate === null || onActivate === void 0 || onActivate();
            var finishActivation = function finishActivation() {
                if (checkCanFocusTrap) {
                    updateTabbableNodes();
                }
                addListeners();
                updateObservedNodes();
                onPostActivate === null || onPostActivate === void 0 || onPostActivate();
            };
            if (checkCanFocusTrap) {
                checkCanFocusTrap(state.containers.concat()).then(finishActivation, finishActivation);
                return this;
            }
            finishActivation();
            return this;
        },
        deactivate: function deactivate(deactivateOptions) {
            if (!state.active) {
                return this;
            }
            var options = _objectSpread2({
                onDeactivate: config.onDeactivate,
                onPostDeactivate: config.onPostDeactivate,
                checkCanReturnFocus: config.checkCanReturnFocus
            }, deactivateOptions);
            clearTimeout(state.delayInitialFocusTimer); // noop if undefined
            state.delayInitialFocusTimer = undefined;
            removeListeners();
            state.active = false;
            state.paused = false;
            updateObservedNodes();
            activeFocusTraps.deactivateTrap(trapStack, trap);
            var onDeactivate = getOption(options, 'onDeactivate');
            var onPostDeactivate = getOption(options, 'onPostDeactivate');
            var checkCanReturnFocus = getOption(options, 'checkCanReturnFocus');
            var returnFocus = getOption(options, 'returnFocus', 'returnFocusOnDeactivate');
            onDeactivate === null || onDeactivate === void 0 || onDeactivate();
            var finishDeactivation = function finishDeactivation() {
                delay(function() {
                    if (returnFocus) {
                        tryFocus(getReturnFocusNode(state.nodeFocusedBeforeActivation));
                    }
                    onPostDeactivate === null || onPostDeactivate === void 0 || onPostDeactivate();
                });
            };
            if (returnFocus && checkCanReturnFocus) {
                checkCanReturnFocus(getReturnFocusNode(state.nodeFocusedBeforeActivation)).then(finishDeactivation, finishDeactivation);
                return this;
            }
            finishDeactivation();
            return this;
        },
        pause: function pause(pauseOptions) {
            if (state.paused || !state.active) {
                return this;
            }
            var onPause = getOption(pauseOptions, 'onPause');
            var onPostPause = getOption(pauseOptions, 'onPostPause');
            state.paused = true;
            onPause === null || onPause === void 0 || onPause();
            removeListeners();
            updateObservedNodes();
            onPostPause === null || onPostPause === void 0 || onPostPause();
            return this;
        },
        unpause: function unpause(unpauseOptions) {
            if (!state.paused || !state.active) {
                return this;
            }
            var onUnpause = getOption(unpauseOptions, 'onUnpause');
            var onPostUnpause = getOption(unpauseOptions, 'onPostUnpause');
            state.paused = false;
            onUnpause === null || onUnpause === void 0 || onUnpause();
            updateTabbableNodes();
            addListeners();
            updateObservedNodes();
            onPostUnpause === null || onPostUnpause === void 0 || onPostUnpause();
            return this;
        },
        updateContainerElements: function updateContainerElements(containerElements) {
            var elementsAsArray = [].concat(containerElements).filter(Boolean);
            state.containers = elementsAsArray.map(function(element) {
                return typeof element === 'string' ? doc.querySelector(element) : element;
            });
            if (state.active) {
                updateTabbableNodes();
            }
            updateObservedNodes();
            return this;
        }
    };
    // initialize container elements
    trap.updateContainerElements(elements);
    return trap;
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/json-schema-traverse/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var traverse = module.exports = function(schema, opts, cb) {
    // Legacy support for v0.3.1 and earlier.
    if (typeof opts == 'function') {
        cb = opts;
        opts = {};
    }
    cb = opts.cb || cb;
    var pre = typeof cb == 'function' ? cb : cb.pre || function() {};
    var post = cb.post || function() {};
    _traverse(opts, pre, post, schema, '', schema);
};
traverse.keywords = {
    additionalItems: true,
    items: true,
    contains: true,
    additionalProperties: true,
    propertyNames: true,
    not: true,
    if: true,
    then: true,
    else: true
};
traverse.arrayKeywords = {
    items: true,
    allOf: true,
    anyOf: true,
    oneOf: true
};
traverse.propsKeywords = {
    $defs: true,
    definitions: true,
    properties: true,
    patternProperties: true,
    dependencies: true
};
traverse.skipKeywords = {
    default: true,
    enum: true,
    const: true,
    required: true,
    maximum: true,
    minimum: true,
    exclusiveMaximum: true,
    exclusiveMinimum: true,
    multipleOf: true,
    maxLength: true,
    minLength: true,
    pattern: true,
    format: true,
    maxItems: true,
    minItems: true,
    uniqueItems: true,
    maxProperties: true,
    minProperties: true
};
function _traverse(opts, pre, post, schema, jsonPtr, rootSchema, parentJsonPtr, parentKeyword, parentSchema, keyIndex) {
    if (schema && typeof schema == 'object' && !Array.isArray(schema)) {
        pre(schema, jsonPtr, rootSchema, parentJsonPtr, parentKeyword, parentSchema, keyIndex);
        for(var key in schema){
            var sch = schema[key];
            if (Array.isArray(sch)) {
                if (key in traverse.arrayKeywords) {
                    for(var i = 0; i < sch.length; i++)_traverse(opts, pre, post, sch[i], jsonPtr + '/' + key + '/' + i, rootSchema, jsonPtr, key, schema, i);
                }
            } else if (key in traverse.propsKeywords) {
                if (sch && typeof sch == 'object') {
                    for(var prop in sch)_traverse(opts, pre, post, sch[prop], jsonPtr + '/' + key + '/' + escapeJsonPtr(prop), rootSchema, jsonPtr, key, schema, prop);
                }
            } else if (key in traverse.keywords || opts.allKeys && !(key in traverse.skipKeywords)) {
                _traverse(opts, pre, post, sch, jsonPtr + '/' + key, rootSchema, jsonPtr, key, schema);
            }
        }
        post(schema, jsonPtr, rootSchema, parentJsonPtr, parentKeyword, parentSchema, keyIndex);
    }
}
function escapeJsonPtr(str) {
    return str.replace(/~/g, '~0').replace(/\//g, '~1');
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/object-assign.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var assign = Object.assign.bind(Object);
module.exports = assign;
module.exports.default = module.exports;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/app-dir/link.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
'use client';
"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    default: null,
    useLinkStatus: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    /**
 * A React component that extends the HTML `<a>` element to provide
 * [prefetching](https://nextjs.org/docs/app/building-your-application/routing/linking-and-navigating#2-prefetching)
 * and client-side navigation. This is the primary way to navigate between routes in Next.js.
 *
 * @remarks
 * - Prefetching is only enabled in production.
 *
 * @see https://nextjs.org/docs/app/api-reference/components/link
 */ default: function() {
        return LinkComponent;
    },
    useLinkStatus: function() {
        return useLinkStatus;
    }
});
const _interop_require_wildcard = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/@swc/helpers/cjs/_interop_require_wildcard.cjs [app-client] (ecmascript)");
const _jsxruntime = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
const _react = /*#__PURE__*/ _interop_require_wildcard._(__turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)"));
const _formaturl = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/format-url.js [app-client] (ecmascript)");
const _approutercontextsharedruntime = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/app-router-context.shared-runtime.js [app-client] (ecmascript)");
const _usemergedref = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/use-merged-ref.js [app-client] (ecmascript)");
const _utils = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils.js [app-client] (ecmascript)");
const _addbasepath = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/add-base-path.js [app-client] (ecmascript)");
const _routerreducertypes = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/router-reducer/router-reducer-types.js [app-client] (ecmascript)");
const _links = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/links.js [app-client] (ecmascript)");
const _islocalurl = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/is-local-url.js [app-client] (ecmascript)");
const _types = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/segment-cache/types.js [app-client] (ecmascript)");
function isModifiedEvent(event) {
    const eventTarget = event.currentTarget;
    const target = eventTarget.getAttribute('target');
    return target && target !== '_self' || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || // triggers resource download
    event.nativeEvent && event.nativeEvent.which === 2;
}
function linkClicked(e, href, linkInstanceRef, replace, scroll, onNavigate, transitionTypes, prefetchIntent = 'none') {
    if (typeof window !== 'undefined') {
        const { nodeName } = e.currentTarget;
        // anchors inside an svg have a lowercase nodeName
        const isAnchorNodeName = nodeName.toUpperCase() === 'A';
        if (isAnchorNodeName && isModifiedEvent(e) || e.currentTarget.hasAttribute('download')) {
            // ignore click for browser’s default behavior
            return;
        }
        if (!(0, _islocalurl.isLocalURL)(href)) {
            if (replace) {
                // browser default behavior does not replace the history state
                // so we need to do it manually
                e.preventDefault();
                location.replace(href);
            }
            // ignore click for browser’s default behavior
            return;
        }
        e.preventDefault();
        if (onNavigate) {
            let isDefaultPrevented = false;
            onNavigate({
                preventDefault: ()=>{
                    isDefaultPrevented = true;
                }
            });
            if (isDefaultPrevented) {
                return;
            }
        }
        const { dispatchNavigateAction } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/app-router-instance.js [app-client] (ecmascript)");
        _react.default.startTransition(()=>{
            dispatchNavigateAction(href, replace ? 'replace' : 'push', scroll === false ? _routerreducertypes.ScrollBehavior.NoScroll : _routerreducertypes.ScrollBehavior.Default, linkInstanceRef.current, transitionTypes, prefetchIntent);
        });
    }
}
function formatStringOrUrl(urlObjOrString) {
    if (typeof urlObjOrString === 'string') {
        return urlObjOrString;
    }
    return (0, _formaturl.formatUrl)(urlObjOrString);
}
function LinkComponent(props) {
    const [linkStatus, setOptimisticLinkStatus] = (0, _react.useOptimistic)(_links.IDLE_LINK_STATUS);
    let children;
    const linkInstanceRef = (0, _react.useRef)(null);
    const { href: hrefProp, as: asProp, children: childrenProp, prefetch: prefetchProp = null, passHref, replace, shallow, scroll, onClick, onMouseEnter: onMouseEnterProp, onTouchStart: onTouchStartProp, legacyBehavior = false, onNavigate, transitionTypes, ref: forwardedRef, unstable_dynamicOnHover, ...restProps } = props;
    children = childrenProp;
    if (legacyBehavior && (typeof children === 'string' || typeof children === 'number')) {
        children = /*#__PURE__*/ (0, _jsxruntime.jsx)("a", {
            children: children
        });
    }
    const router = _react.default.useContext(_approutercontextsharedruntime.AppRouterContext);
    const prefetchEnabled = prefetchProp !== false;
    const prefetchIntent = prefetchProp === false ? 'none' : prefetchProp === true ? 'full' : 'auto';
    const fetchStrategy = prefetchIntent !== 'none' ? getFetchStrategyFromPrefetchIntent(prefetchIntent) : _types.FetchStrategy.PPR;
    if ("TURBOPACK compile-time truthy", 1) {
        function createPropError(args) {
            return Object.defineProperty(new Error(`Failed prop type: The prop \`${args.key}\` expects a ${args.expected} in \`<Link>\`, but got \`${args.actual}\` instead.` + (typeof window !== 'undefined' ? "\nOpen your browser's console to view the Component stack trace." : '')), "__NEXT_ERROR_CODE", {
                value: "E319",
                enumerable: false,
                configurable: true
            });
        }
        // TypeScript trick for type-guarding:
        const requiredPropsGuard = {
            href: true
        };
        const requiredProps = Object.keys(requiredPropsGuard);
        requiredProps.forEach((key)=>{
            if (key === 'href') {
                if (props[key] == null || typeof props[key] !== 'string' && typeof props[key] !== 'object') {
                    throw createPropError({
                        key,
                        expected: '`string` or `object`',
                        actual: props[key] === null ? 'null' : typeof props[key]
                    });
                }
            } else {
                // TypeScript trick for type-guarding:
                const _ = key;
            }
        });
        // TypeScript trick for type-guarding:
        const optionalPropsGuard = {
            as: true,
            replace: true,
            scroll: true,
            shallow: true,
            passHref: true,
            prefetch: true,
            unstable_dynamicOnHover: true,
            onClick: true,
            onMouseEnter: true,
            onTouchStart: true,
            legacyBehavior: true,
            onNavigate: true,
            transitionTypes: true
        };
        const optionalProps = Object.keys(optionalPropsGuard);
        optionalProps.forEach((key)=>{
            const valType = typeof props[key];
            if (key === 'as') {
                if (props[key] && valType !== 'string' && valType !== 'object') {
                    throw createPropError({
                        key,
                        expected: '`string` or `object`',
                        actual: valType
                    });
                }
            } else if (key === 'onClick' || key === 'onMouseEnter' || key === 'onTouchStart' || key === 'onNavigate') {
                if (props[key] && valType !== 'function') {
                    throw createPropError({
                        key,
                        expected: '`function`',
                        actual: valType
                    });
                }
            } else if (key === 'replace' || key === 'scroll' || key === 'shallow' || key === 'passHref' || key === 'legacyBehavior' || key === 'unstable_dynamicOnHover') {
                if (props[key] != null && valType !== 'boolean') {
                    throw createPropError({
                        key,
                        expected: '`boolean`',
                        actual: valType
                    });
                }
            } else if (key === 'prefetch') {
                if (props[key] != null && valType !== 'boolean' && props[key] !== 'auto') {
                    throw createPropError({
                        key,
                        expected: '`boolean | "auto"`',
                        actual: valType
                    });
                }
            } else if (key === 'transitionTypes') {
                if (props[key] != null && !Array.isArray(props[key])) {
                    throw createPropError({
                        key,
                        expected: '`string[]`',
                        actual: valType
                    });
                }
            } else {
                // TypeScript trick for type-guarding:
                const _ = key;
            }
        });
    }
    const resolvedHref = asProp || hrefProp;
    const formattedHref = formatStringOrUrl(resolvedHref);
    if ("TURBOPACK compile-time truthy", 1) {
        const { warnOnce } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils/warn-once.js [app-client] (ecmascript)");
        if (props.locale) {
            warnOnce('The `locale` prop is not supported in `next/link` while using the `app` router. Read more about app router internalization: https://nextjs.org/docs/app/building-your-application/routing/internationalization');
        }
        if (!asProp) {
            let href;
            if (typeof resolvedHref === 'string') {
                href = resolvedHref;
            } else if (typeof resolvedHref === 'object' && typeof resolvedHref.pathname === 'string') {
                href = resolvedHref.pathname;
            }
            if (href) {
                const hasDynamicSegment = href.split('/').some((segment)=>segment.startsWith('[') && segment.endsWith(']'));
                if (hasDynamicSegment) {
                    throw Object.defineProperty(new Error(`Dynamic href \`${href}\` found in <Link> while using the \`/app\` router, this is not supported. Read more: https://nextjs.org/docs/messages/app-dir-dynamic-href`), "__NEXT_ERROR_CODE", {
                        value: "E267",
                        enumerable: false,
                        configurable: true
                    });
                }
            }
        }
    }
    // This will return the first child, if multiple are provided it will throw an error
    let child;
    if (legacyBehavior) {
        if (children?.$$typeof === Symbol.for('react.lazy')) {
            throw Object.defineProperty(new Error(`\`<Link legacyBehavior>\` received a direct child that is either a Server Component, or JSX that was loaded with React.lazy(). This is not supported. Either remove legacyBehavior, or make the direct child a Client Component that renders the Link's \`<a>\` tag.`), "__NEXT_ERROR_CODE", {
                value: "E863",
                enumerable: false,
                configurable: true
            });
        }
        if ("TURBOPACK compile-time truthy", 1) {
            if (onClick) {
                console.warn(`"onClick" was passed to <Link> with \`href\` of \`${formattedHref}\` but "legacyBehavior" was set. The legacy behavior requires onClick be set on the child of next/link`);
            }
            if (onMouseEnterProp) {
                console.warn(`"onMouseEnter" was passed to <Link> with \`href\` of \`${formattedHref}\` but "legacyBehavior" was set. The legacy behavior requires onMouseEnter be set on the child of next/link`);
            }
            try {
                child = _react.default.Children.only(children);
            } catch (err) {
                if (!children) {
                    throw Object.defineProperty(new Error(`No children were passed to <Link> with \`href\` of \`${formattedHref}\` but one child is required https://nextjs.org/docs/messages/link-no-children`), "__NEXT_ERROR_CODE", {
                        value: "E320",
                        enumerable: false,
                        configurable: true
                    });
                }
                throw Object.defineProperty(new Error(`Multiple children were passed to <Link> with \`href\` of \`${formattedHref}\` but only one child is supported https://nextjs.org/docs/messages/link-multiple-children` + (typeof window !== 'undefined' ? " \nOpen your browser's console to view the Component stack trace." : '')), "__NEXT_ERROR_CODE", {
                    value: "E266",
                    enumerable: false,
                    configurable: true
                });
            }
        } else //TURBOPACK unreachable
        ;
    } else {
        if ("TURBOPACK compile-time truthy", 1) {
            if (children?.type === 'a') {
                throw Object.defineProperty(new Error('Invalid <Link> with <a> child. Please remove <a> or use <Link legacyBehavior>.\nLearn more: https://nextjs.org/docs/messages/invalid-new-link-with-extra-anchor'), "__NEXT_ERROR_CODE", {
                    value: "E209",
                    enumerable: false,
                    configurable: true
                });
            }
        }
    }
    const childRef = legacyBehavior ? child && typeof child === 'object' && child.ref : forwardedRef;
    // Capture the Owner Stack during render so dev-only warnings emitted later
    // at navigation time can be associated with the JSX that created
    // this <Link>.
    const ownerStack = ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : undefined;
    // Use a callback ref to attach an IntersectionObserver to the anchor tag on
    // mount. In the future we will also use this to keep track of all the
    // currently mounted <Link> instances, e.g. so we can re-prefetch them after
    // a revalidation or refresh.
    const observeLinkVisibilityOnMount = _react.default.useCallback({
        "LinkComponent.useCallback[observeLinkVisibilityOnMount]": (element)=>{
            if (router !== null) {
                linkInstanceRef.current = (0, _links.mountLinkInstance)(element, formattedHref, router, fetchStrategy, prefetchEnabled, setOptimisticLinkStatus, ownerStack);
            }
            return ({
                "LinkComponent.useCallback[observeLinkVisibilityOnMount]": ()=>{
                    if (linkInstanceRef.current) {
                        (0, _links.unmountLinkForCurrentNavigation)(linkInstanceRef.current);
                        linkInstanceRef.current = null;
                    }
                    (0, _links.unmountPrefetchableInstance)(element);
                }
            })["LinkComponent.useCallback[observeLinkVisibilityOnMount]"];
        }
    }["LinkComponent.useCallback[observeLinkVisibilityOnMount]"], [
        prefetchEnabled,
        formattedHref,
        router,
        fetchStrategy,
        setOptimisticLinkStatus,
        ownerStack
    ]);
    const mergedRef = (0, _usemergedref.useMergedRef)(observeLinkVisibilityOnMount, childRef);
    const childProps = {
        ref: mergedRef,
        onClick (e) {
            if ("TURBOPACK compile-time truthy", 1) {
                if (!e) {
                    throw Object.defineProperty(new Error(`Component rendered inside next/link has to pass click event to "onClick" prop.`), "__NEXT_ERROR_CODE", {
                        value: "E312",
                        enumerable: false,
                        configurable: true
                    });
                }
            }
            if (!legacyBehavior && typeof onClick === 'function') {
                onClick(e);
            }
            if (legacyBehavior && child.props && typeof child.props.onClick === 'function') {
                child.props.onClick(e);
            }
            if (!router) {
                return;
            }
            if (e.defaultPrevented) {
                return;
            }
            linkClicked(e, formattedHref, linkInstanceRef, replace, scroll, onNavigate, transitionTypes, prefetchIntent);
        },
        onMouseEnter (e) {
            if (!legacyBehavior && typeof onMouseEnterProp === 'function') {
                onMouseEnterProp(e);
            }
            if (legacyBehavior && child.props && typeof child.props.onMouseEnter === 'function') {
                child.props.onMouseEnter(e);
            }
            if (!router) {
                return;
            }
            if ("TURBOPACK compile-time truthy", 1) {
                return;
            }
            //TURBOPACK unreachable
            ;
            const upgradeToDynamicPrefetch = undefined;
        },
        onTouchStart: ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : function onTouchStart(e) {
            if (!legacyBehavior && typeof onTouchStartProp === 'function') {
                onTouchStartProp(e);
            }
            if (legacyBehavior && child.props && typeof child.props.onTouchStart === 'function') {
                child.props.onTouchStart(e);
            }
            if (!router) {
                return;
            }
            if (!prefetchEnabled) {
                return;
            }
            const upgradeToDynamicPrefetch = unstable_dynamicOnHover === true;
            (0, _links.onNavigationIntent)(e.currentTarget, upgradeToDynamicPrefetch);
        }
    };
    // If the url is absolute, we can bypass the logic to prepend the basePath.
    if ((0, _utils.isAbsoluteUrl)(formattedHref)) {
        childProps.href = formattedHref;
    } else if (!legacyBehavior || passHref || child.type === 'a' && !('href' in child.props)) {
        childProps.href = (0, _addbasepath.addBasePath)(formattedHref);
    }
    let link;
    if (legacyBehavior) {
        if ("TURBOPACK compile-time truthy", 1) {
            const { errorOnce } = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils/error-once.js [app-client] (ecmascript)");
            errorOnce('`legacyBehavior` is deprecated and will be removed in a future ' + 'release. A codemod is available to upgrade your components:\n\n' + 'npx @next/codemod@latest new-link .\n\n' + 'Learn more: https://nextjs.org/docs/app/building-your-application/upgrading/codemods#remove-a-tags-from-link-components');
        }
        link = /*#__PURE__*/ _react.default.cloneElement(child, childProps);
    } else {
        link = /*#__PURE__*/ (0, _jsxruntime.jsx)("a", {
            ...restProps,
            ...childProps,
            children: children
        });
    }
    return /*#__PURE__*/ (0, _jsxruntime.jsx)(LinkStatusContext.Provider, {
        value: linkStatus,
        children: link
    });
}
const LinkStatusContext = /*#__PURE__*/ (0, _react.createContext)(_links.IDLE_LINK_STATUS);
const useLinkStatus = ()=>{
    return (0, _react.useContext)(LinkStatusContext);
};
function getFetchStrategyFromPrefetchIntent(prefetchIntent) {
    if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
    ;
    else {
        return prefetchIntent === 'auto' ? _types.FetchStrategy.PPR : _types.FetchStrategy.Full;
    }
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/use-merged-ref.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "useMergedRef", {
    enumerable: true,
    get: function() {
        return useMergedRef;
    }
});
const _react = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
function useMergedRef(refA, refB) {
    const cleanupA = (0, _react.useRef)(null);
    const cleanupB = (0, _react.useRef)(null);
    // NOTE: In theory, we could skip the wrapping if only one of the refs is non-null.
    // (this happens often if the user doesn't pass a ref to Link/Form/Image)
    // But this can cause us to leak a cleanup-ref into user code (previously via `<Link legacyBehavior>`),
    // and the user might pass that ref into ref-merging library that doesn't support cleanup refs
    // (because it hasn't been updated for React 19)
    // which can then cause things to blow up, because a cleanup-returning ref gets called with `null`.
    // So in practice, it's safer to be defensive and always wrap the ref, even on React 19.
    return (0, _react.useCallback)((current)=>{
        if (current === null) {
            const cleanupFnA = cleanupA.current;
            if (cleanupFnA) {
                cleanupA.current = null;
                cleanupFnA();
            }
            const cleanupFnB = cleanupB.current;
            if (cleanupFnB) {
                cleanupB.current = null;
                cleanupFnB();
            }
        } else {
            if (refA) {
                cleanupA.current = applyRef(refA, current);
            }
            if (refB) {
                cleanupB.current = applyRef(refB, current);
            }
        }
    }, [
        refA,
        refB
    ]);
}
function applyRef(refA, current) {
    if (typeof refA === 'function') {
        const cleanup = refA(current);
        if (typeof cleanup === 'function') {
            return cleanup;
        } else {
            return ()=>refA(null);
        }
    } else {
        refA.current = current;
        return ()=>{
            refA.current = null;
        };
    }
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/buffer/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

(function() {
    var e = {
        872: function(e, r) {
            "use strict";
            r.byteLength = byteLength;
            r.toByteArray = toByteArray;
            r.fromByteArray = fromByteArray;
            var t = [];
            var f = [];
            var n = typeof Uint8Array !== "undefined" ? Uint8Array : Array;
            var i = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
            for(var o = 0, u = i.length; o < u; ++o){
                t[o] = i[o];
                f[i.charCodeAt(o)] = o;
            }
            f["-".charCodeAt(0)] = 62;
            f["_".charCodeAt(0)] = 63;
            function getLens(e) {
                var r = e.length;
                if (r % 4 > 0) {
                    throw new Error("Invalid string. Length must be a multiple of 4");
                }
                var t = e.indexOf("=");
                if (t === -1) t = r;
                var f = t === r ? 0 : 4 - t % 4;
                return [
                    t,
                    f
                ];
            }
            function byteLength(e) {
                var r = getLens(e);
                var t = r[0];
                var f = r[1];
                return (t + f) * 3 / 4 - f;
            }
            function _byteLength(e, r, t) {
                return (r + t) * 3 / 4 - t;
            }
            function toByteArray(e) {
                var r;
                var t = getLens(e);
                var i = t[0];
                var o = t[1];
                var u = new n(_byteLength(e, i, o));
                var a = 0;
                var s = o > 0 ? i - 4 : i;
                var h;
                for(h = 0; h < s; h += 4){
                    r = f[e.charCodeAt(h)] << 18 | f[e.charCodeAt(h + 1)] << 12 | f[e.charCodeAt(h + 2)] << 6 | f[e.charCodeAt(h + 3)];
                    u[a++] = r >> 16 & 255;
                    u[a++] = r >> 8 & 255;
                    u[a++] = r & 255;
                }
                if (o === 2) {
                    r = f[e.charCodeAt(h)] << 2 | f[e.charCodeAt(h + 1)] >> 4;
                    u[a++] = r & 255;
                }
                if (o === 1) {
                    r = f[e.charCodeAt(h)] << 10 | f[e.charCodeAt(h + 1)] << 4 | f[e.charCodeAt(h + 2)] >> 2;
                    u[a++] = r >> 8 & 255;
                    u[a++] = r & 255;
                }
                return u;
            }
            function tripletToBase64(e) {
                return t[e >> 18 & 63] + t[e >> 12 & 63] + t[e >> 6 & 63] + t[e & 63];
            }
            function encodeChunk(e, r, t) {
                var f;
                var n = [];
                for(var i = r; i < t; i += 3){
                    f = (e[i] << 16 & 16711680) + (e[i + 1] << 8 & 65280) + (e[i + 2] & 255);
                    n.push(tripletToBase64(f));
                }
                return n.join("");
            }
            function fromByteArray(e) {
                var r;
                var f = e.length;
                var n = f % 3;
                var i = [];
                var o = 16383;
                for(var u = 0, a = f - n; u < a; u += o){
                    i.push(encodeChunk(e, u, u + o > a ? a : u + o));
                }
                if (n === 1) {
                    r = e[f - 1];
                    i.push(t[r >> 2] + t[r << 4 & 63] + "==");
                } else if (n === 2) {
                    r = (e[f - 2] << 8) + e[f - 1];
                    i.push(t[r >> 10] + t[r >> 4 & 63] + t[r << 2 & 63] + "=");
                }
                return i.join("");
            }
        },
        230: function(e, r, t) {
            "use strict";
            /*!
 * The buffer module from node.js, for the browser.
 *
 * @author   Feross Aboukhadijeh <https://feross.org>
 * @license  MIT
 */ var f = t(872);
            var n = t(321);
            var i = typeof Symbol === "function" && typeof Symbol.for === "function" ? Symbol.for("nodejs.util.inspect.custom") : null;
            r.Buffer = Buffer;
            r.SlowBuffer = SlowBuffer;
            r.INSPECT_MAX_BYTES = 50;
            var o = 2147483647;
            r.kMaxLength = o;
            Buffer.TYPED_ARRAY_SUPPORT = typedArraySupport();
            if (!Buffer.TYPED_ARRAY_SUPPORT && typeof console !== "undefined" && typeof console.error === "function") {
                console.error("This browser lacks typed array (Uint8Array) support which is required by " + "`buffer` v5.x. Use `buffer` v4.x if you require old browser support.");
            }
            function typedArraySupport() {
                try {
                    var e = new Uint8Array(1);
                    var r = {
                        foo: function() {
                            return 42;
                        }
                    };
                    Object.setPrototypeOf(r, Uint8Array.prototype);
                    Object.setPrototypeOf(e, r);
                    return e.foo() === 42;
                } catch (e) {
                    return false;
                }
            }
            Object.defineProperty(Buffer.prototype, "parent", {
                enumerable: true,
                get: function() {
                    if (!Buffer.isBuffer(this)) return undefined;
                    return this.buffer;
                }
            });
            Object.defineProperty(Buffer.prototype, "offset", {
                enumerable: true,
                get: function() {
                    if (!Buffer.isBuffer(this)) return undefined;
                    return this.byteOffset;
                }
            });
            function createBuffer(e) {
                if (e > o) {
                    throw new RangeError('The value "' + e + '" is invalid for option "size"');
                }
                var r = new Uint8Array(e);
                Object.setPrototypeOf(r, Buffer.prototype);
                return r;
            }
            function Buffer(e, r, t) {
                if (typeof e === "number") {
                    if (typeof r === "string") {
                        throw new TypeError('The "string" argument must be of type string. Received type number');
                    }
                    return allocUnsafe(e);
                }
                return from(e, r, t);
            }
            Buffer.poolSize = 8192;
            function from(e, r, t) {
                if (typeof e === "string") {
                    return fromString(e, r);
                }
                if (ArrayBuffer.isView(e)) {
                    return fromArrayLike(e);
                }
                if (e == null) {
                    throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, " + "or Array-like Object. Received type " + typeof e);
                }
                if (isInstance(e, ArrayBuffer) || e && isInstance(e.buffer, ArrayBuffer)) {
                    return fromArrayBuffer(e, r, t);
                }
                if (typeof SharedArrayBuffer !== "undefined" && (isInstance(e, SharedArrayBuffer) || e && isInstance(e.buffer, SharedArrayBuffer))) {
                    return fromArrayBuffer(e, r, t);
                }
                if (typeof e === "number") {
                    throw new TypeError('The "value" argument must not be of type number. Received type number');
                }
                var f = e.valueOf && e.valueOf();
                if (f != null && f !== e) {
                    return Buffer.from(f, r, t);
                }
                var n = fromObject(e);
                if (n) return n;
                if (typeof Symbol !== "undefined" && Symbol.toPrimitive != null && typeof e[Symbol.toPrimitive] === "function") {
                    return Buffer.from(e[Symbol.toPrimitive]("string"), r, t);
                }
                throw new TypeError("The first argument must be one of type string, Buffer, ArrayBuffer, Array, " + "or Array-like Object. Received type " + typeof e);
            }
            Buffer.from = function(e, r, t) {
                return from(e, r, t);
            };
            Object.setPrototypeOf(Buffer.prototype, Uint8Array.prototype);
            Object.setPrototypeOf(Buffer, Uint8Array);
            function assertSize(e) {
                if (typeof e !== "number") {
                    throw new TypeError('"size" argument must be of type number');
                } else if (e < 0) {
                    throw new RangeError('The value "' + e + '" is invalid for option "size"');
                }
            }
            function alloc(e, r, t) {
                assertSize(e);
                if (e <= 0) {
                    return createBuffer(e);
                }
                if (r !== undefined) {
                    return typeof t === "string" ? createBuffer(e).fill(r, t) : createBuffer(e).fill(r);
                }
                return createBuffer(e);
            }
            Buffer.alloc = function(e, r, t) {
                return alloc(e, r, t);
            };
            function allocUnsafe(e) {
                assertSize(e);
                return createBuffer(e < 0 ? 0 : checked(e) | 0);
            }
            Buffer.allocUnsafe = function(e) {
                return allocUnsafe(e);
            };
            Buffer.allocUnsafeSlow = function(e) {
                return allocUnsafe(e);
            };
            function fromString(e, r) {
                if (typeof r !== "string" || r === "") {
                    r = "utf8";
                }
                if (!Buffer.isEncoding(r)) {
                    throw new TypeError("Unknown encoding: " + r);
                }
                var t = byteLength(e, r) | 0;
                var f = createBuffer(t);
                var n = f.write(e, r);
                if (n !== t) {
                    f = f.slice(0, n);
                }
                return f;
            }
            function fromArrayLike(e) {
                var r = e.length < 0 ? 0 : checked(e.length) | 0;
                var t = createBuffer(r);
                for(var f = 0; f < r; f += 1){
                    t[f] = e[f] & 255;
                }
                return t;
            }
            function fromArrayBuffer(e, r, t) {
                if (r < 0 || e.byteLength < r) {
                    throw new RangeError('"offset" is outside of buffer bounds');
                }
                if (e.byteLength < r + (t || 0)) {
                    throw new RangeError('"length" is outside of buffer bounds');
                }
                var f;
                if (r === undefined && t === undefined) {
                    f = new Uint8Array(e);
                } else if (t === undefined) {
                    f = new Uint8Array(e, r);
                } else {
                    f = new Uint8Array(e, r, t);
                }
                Object.setPrototypeOf(f, Buffer.prototype);
                return f;
            }
            function fromObject(e) {
                if (Buffer.isBuffer(e)) {
                    var r = checked(e.length) | 0;
                    var t = createBuffer(r);
                    if (t.length === 0) {
                        return t;
                    }
                    e.copy(t, 0, 0, r);
                    return t;
                }
                if (e.length !== undefined) {
                    if (typeof e.length !== "number" || numberIsNaN(e.length)) {
                        return createBuffer(0);
                    }
                    return fromArrayLike(e);
                }
                if (e.type === "Buffer" && Array.isArray(e.data)) {
                    return fromArrayLike(e.data);
                }
            }
            function checked(e) {
                if (e >= o) {
                    throw new RangeError("Attempt to allocate Buffer larger than maximum " + "size: 0x" + o.toString(16) + " bytes");
                }
                return e | 0;
            }
            function SlowBuffer(e) {
                if (+e != e) {
                    e = 0;
                }
                return Buffer.alloc(+e);
            }
            Buffer.isBuffer = function isBuffer(e) {
                return e != null && e._isBuffer === true && e !== Buffer.prototype;
            };
            Buffer.compare = function compare(e, r) {
                if (isInstance(e, Uint8Array)) e = Buffer.from(e, e.offset, e.byteLength);
                if (isInstance(r, Uint8Array)) r = Buffer.from(r, r.offset, r.byteLength);
                if (!Buffer.isBuffer(e) || !Buffer.isBuffer(r)) {
                    throw new TypeError('The "buf1", "buf2" arguments must be one of type Buffer or Uint8Array');
                }
                if (e === r) return 0;
                var t = e.length;
                var f = r.length;
                for(var n = 0, i = Math.min(t, f); n < i; ++n){
                    if (e[n] !== r[n]) {
                        t = e[n];
                        f = r[n];
                        break;
                    }
                }
                if (t < f) return -1;
                if (f < t) return 1;
                return 0;
            };
            Buffer.isEncoding = function isEncoding(e) {
                switch(String(e).toLowerCase()){
                    case "hex":
                    case "utf8":
                    case "utf-8":
                    case "ascii":
                    case "latin1":
                    case "binary":
                    case "base64":
                    case "ucs2":
                    case "ucs-2":
                    case "utf16le":
                    case "utf-16le":
                        return true;
                    default:
                        return false;
                }
            };
            Buffer.concat = function concat(e, r) {
                if (!Array.isArray(e)) {
                    throw new TypeError('"list" argument must be an Array of Buffers');
                }
                if (e.length === 0) {
                    return Buffer.alloc(0);
                }
                var t;
                if (r === undefined) {
                    r = 0;
                    for(t = 0; t < e.length; ++t){
                        r += e[t].length;
                    }
                }
                var f = Buffer.allocUnsafe(r);
                var n = 0;
                for(t = 0; t < e.length; ++t){
                    var i = e[t];
                    if (isInstance(i, Uint8Array)) {
                        i = Buffer.from(i);
                    }
                    if (!Buffer.isBuffer(i)) {
                        throw new TypeError('"list" argument must be an Array of Buffers');
                    }
                    i.copy(f, n);
                    n += i.length;
                }
                return f;
            };
            function byteLength(e, r) {
                if (Buffer.isBuffer(e)) {
                    return e.length;
                }
                if (ArrayBuffer.isView(e) || isInstance(e, ArrayBuffer)) {
                    return e.byteLength;
                }
                if (typeof e !== "string") {
                    throw new TypeError('The "string" argument must be one of type string, Buffer, or ArrayBuffer. ' + "Received type " + typeof e);
                }
                var t = e.length;
                var f = arguments.length > 2 && arguments[2] === true;
                if (!f && t === 0) return 0;
                var n = false;
                for(;;){
                    switch(r){
                        case "ascii":
                        case "latin1":
                        case "binary":
                            return t;
                        case "utf8":
                        case "utf-8":
                            return utf8ToBytes(e).length;
                        case "ucs2":
                        case "ucs-2":
                        case "utf16le":
                        case "utf-16le":
                            return t * 2;
                        case "hex":
                            return t >>> 1;
                        case "base64":
                            return base64ToBytes(e).length;
                        default:
                            if (n) {
                                return f ? -1 : utf8ToBytes(e).length;
                            }
                            r = ("" + r).toLowerCase();
                            n = true;
                    }
                }
            }
            Buffer.byteLength = byteLength;
            function slowToString(e, r, t) {
                var f = false;
                if (r === undefined || r < 0) {
                    r = 0;
                }
                if (r > this.length) {
                    return "";
                }
                if (t === undefined || t > this.length) {
                    t = this.length;
                }
                if (t <= 0) {
                    return "";
                }
                t >>>= 0;
                r >>>= 0;
                if (t <= r) {
                    return "";
                }
                if (!e) e = "utf8";
                while(true){
                    switch(e){
                        case "hex":
                            return hexSlice(this, r, t);
                        case "utf8":
                        case "utf-8":
                            return utf8Slice(this, r, t);
                        case "ascii":
                            return asciiSlice(this, r, t);
                        case "latin1":
                        case "binary":
                            return latin1Slice(this, r, t);
                        case "base64":
                            return base64Slice(this, r, t);
                        case "ucs2":
                        case "ucs-2":
                        case "utf16le":
                        case "utf-16le":
                            return utf16leSlice(this, r, t);
                        default:
                            if (f) throw new TypeError("Unknown encoding: " + e);
                            e = (e + "").toLowerCase();
                            f = true;
                    }
                }
            }
            Buffer.prototype._isBuffer = true;
            function swap(e, r, t) {
                var f = e[r];
                e[r] = e[t];
                e[t] = f;
            }
            Buffer.prototype.swap16 = function swap16() {
                var e = this.length;
                if (e % 2 !== 0) {
                    throw new RangeError("Buffer size must be a multiple of 16-bits");
                }
                for(var r = 0; r < e; r += 2){
                    swap(this, r, r + 1);
                }
                return this;
            };
            Buffer.prototype.swap32 = function swap32() {
                var e = this.length;
                if (e % 4 !== 0) {
                    throw new RangeError("Buffer size must be a multiple of 32-bits");
                }
                for(var r = 0; r < e; r += 4){
                    swap(this, r, r + 3);
                    swap(this, r + 1, r + 2);
                }
                return this;
            };
            Buffer.prototype.swap64 = function swap64() {
                var e = this.length;
                if (e % 8 !== 0) {
                    throw new RangeError("Buffer size must be a multiple of 64-bits");
                }
                for(var r = 0; r < e; r += 8){
                    swap(this, r, r + 7);
                    swap(this, r + 1, r + 6);
                    swap(this, r + 2, r + 5);
                    swap(this, r + 3, r + 4);
                }
                return this;
            };
            Buffer.prototype.toString = function toString() {
                var e = this.length;
                if (e === 0) return "";
                if (arguments.length === 0) return utf8Slice(this, 0, e);
                return slowToString.apply(this, arguments);
            };
            Buffer.prototype.toLocaleString = Buffer.prototype.toString;
            Buffer.prototype.equals = function equals(e) {
                if (!Buffer.isBuffer(e)) throw new TypeError("Argument must be a Buffer");
                if (this === e) return true;
                return Buffer.compare(this, e) === 0;
            };
            Buffer.prototype.inspect = function inspect() {
                var e = "";
                var t = r.INSPECT_MAX_BYTES;
                e = this.toString("hex", 0, t).replace(/(.{2})/g, "$1 ").trim();
                if (this.length > t) e += " ... ";
                return "<Buffer " + e + ">";
            };
            if (i) {
                Buffer.prototype[i] = Buffer.prototype.inspect;
            }
            Buffer.prototype.compare = function compare(e, r, t, f, n) {
                if (isInstance(e, Uint8Array)) {
                    e = Buffer.from(e, e.offset, e.byteLength);
                }
                if (!Buffer.isBuffer(e)) {
                    throw new TypeError('The "target" argument must be one of type Buffer or Uint8Array. ' + "Received type " + typeof e);
                }
                if (r === undefined) {
                    r = 0;
                }
                if (t === undefined) {
                    t = e ? e.length : 0;
                }
                if (f === undefined) {
                    f = 0;
                }
                if (n === undefined) {
                    n = this.length;
                }
                if (r < 0 || t > e.length || f < 0 || n > this.length) {
                    throw new RangeError("out of range index");
                }
                if (f >= n && r >= t) {
                    return 0;
                }
                if (f >= n) {
                    return -1;
                }
                if (r >= t) {
                    return 1;
                }
                r >>>= 0;
                t >>>= 0;
                f >>>= 0;
                n >>>= 0;
                if (this === e) return 0;
                var i = n - f;
                var o = t - r;
                var u = Math.min(i, o);
                var a = this.slice(f, n);
                var s = e.slice(r, t);
                for(var h = 0; h < u; ++h){
                    if (a[h] !== s[h]) {
                        i = a[h];
                        o = s[h];
                        break;
                    }
                }
                if (i < o) return -1;
                if (o < i) return 1;
                return 0;
            };
            function bidirectionalIndexOf(e, r, t, f, n) {
                if (e.length === 0) return -1;
                if (typeof t === "string") {
                    f = t;
                    t = 0;
                } else if (t > 2147483647) {
                    t = 2147483647;
                } else if (t < -2147483648) {
                    t = -2147483648;
                }
                t = +t;
                if (numberIsNaN(t)) {
                    t = n ? 0 : e.length - 1;
                }
                if (t < 0) t = e.length + t;
                if (t >= e.length) {
                    if (n) return -1;
                    else t = e.length - 1;
                } else if (t < 0) {
                    if (n) t = 0;
                    else return -1;
                }
                if (typeof r === "string") {
                    r = Buffer.from(r, f);
                }
                if (Buffer.isBuffer(r)) {
                    if (r.length === 0) {
                        return -1;
                    }
                    return arrayIndexOf(e, r, t, f, n);
                } else if (typeof r === "number") {
                    r = r & 255;
                    if (typeof Uint8Array.prototype.indexOf === "function") {
                        if (n) {
                            return Uint8Array.prototype.indexOf.call(e, r, t);
                        } else {
                            return Uint8Array.prototype.lastIndexOf.call(e, r, t);
                        }
                    }
                    return arrayIndexOf(e, [
                        r
                    ], t, f, n);
                }
                throw new TypeError("val must be string, number or Buffer");
            }
            function arrayIndexOf(e, r, t, f, n) {
                var i = 1;
                var o = e.length;
                var u = r.length;
                if (f !== undefined) {
                    f = String(f).toLowerCase();
                    if (f === "ucs2" || f === "ucs-2" || f === "utf16le" || f === "utf-16le") {
                        if (e.length < 2 || r.length < 2) {
                            return -1;
                        }
                        i = 2;
                        o /= 2;
                        u /= 2;
                        t /= 2;
                    }
                }
                function read(e, r) {
                    if (i === 1) {
                        return e[r];
                    } else {
                        return e.readUInt16BE(r * i);
                    }
                }
                var a;
                if (n) {
                    var s = -1;
                    for(a = t; a < o; a++){
                        if (read(e, a) === read(r, s === -1 ? 0 : a - s)) {
                            if (s === -1) s = a;
                            if (a - s + 1 === u) return s * i;
                        } else {
                            if (s !== -1) a -= a - s;
                            s = -1;
                        }
                    }
                } else {
                    if (t + u > o) t = o - u;
                    for(a = t; a >= 0; a--){
                        var h = true;
                        for(var c = 0; c < u; c++){
                            if (read(e, a + c) !== read(r, c)) {
                                h = false;
                                break;
                            }
                        }
                        if (h) return a;
                    }
                }
                return -1;
            }
            Buffer.prototype.includes = function includes(e, r, t) {
                return this.indexOf(e, r, t) !== -1;
            };
            Buffer.prototype.indexOf = function indexOf(e, r, t) {
                return bidirectionalIndexOf(this, e, r, t, true);
            };
            Buffer.prototype.lastIndexOf = function lastIndexOf(e, r, t) {
                return bidirectionalIndexOf(this, e, r, t, false);
            };
            function hexWrite(e, r, t, f) {
                t = Number(t) || 0;
                var n = e.length - t;
                if (!f) {
                    f = n;
                } else {
                    f = Number(f);
                    if (f > n) {
                        f = n;
                    }
                }
                var i = r.length;
                if (f > i / 2) {
                    f = i / 2;
                }
                for(var o = 0; o < f; ++o){
                    var u = parseInt(r.substr(o * 2, 2), 16);
                    if (numberIsNaN(u)) return o;
                    e[t + o] = u;
                }
                return o;
            }
            function utf8Write(e, r, t, f) {
                return blitBuffer(utf8ToBytes(r, e.length - t), e, t, f);
            }
            function asciiWrite(e, r, t, f) {
                return blitBuffer(asciiToBytes(r), e, t, f);
            }
            function latin1Write(e, r, t, f) {
                return asciiWrite(e, r, t, f);
            }
            function base64Write(e, r, t, f) {
                return blitBuffer(base64ToBytes(r), e, t, f);
            }
            function ucs2Write(e, r, t, f) {
                return blitBuffer(utf16leToBytes(r, e.length - t), e, t, f);
            }
            Buffer.prototype.write = function write(e, r, t, f) {
                if (r === undefined) {
                    f = "utf8";
                    t = this.length;
                    r = 0;
                } else if (t === undefined && typeof r === "string") {
                    f = r;
                    t = this.length;
                    r = 0;
                } else if (isFinite(r)) {
                    r = r >>> 0;
                    if (isFinite(t)) {
                        t = t >>> 0;
                        if (f === undefined) f = "utf8";
                    } else {
                        f = t;
                        t = undefined;
                    }
                } else {
                    throw new Error("Buffer.write(string, encoding, offset[, length]) is no longer supported");
                }
                var n = this.length - r;
                if (t === undefined || t > n) t = n;
                if (e.length > 0 && (t < 0 || r < 0) || r > this.length) {
                    throw new RangeError("Attempt to write outside buffer bounds");
                }
                if (!f) f = "utf8";
                var i = false;
                for(;;){
                    switch(f){
                        case "hex":
                            return hexWrite(this, e, r, t);
                        case "utf8":
                        case "utf-8":
                            return utf8Write(this, e, r, t);
                        case "ascii":
                            return asciiWrite(this, e, r, t);
                        case "latin1":
                        case "binary":
                            return latin1Write(this, e, r, t);
                        case "base64":
                            return base64Write(this, e, r, t);
                        case "ucs2":
                        case "ucs-2":
                        case "utf16le":
                        case "utf-16le":
                            return ucs2Write(this, e, r, t);
                        default:
                            if (i) throw new TypeError("Unknown encoding: " + f);
                            f = ("" + f).toLowerCase();
                            i = true;
                    }
                }
            };
            Buffer.prototype.toJSON = function toJSON() {
                return {
                    type: "Buffer",
                    data: Array.prototype.slice.call(this._arr || this, 0)
                };
            };
            function base64Slice(e, r, t) {
                if (r === 0 && t === e.length) {
                    return f.fromByteArray(e);
                } else {
                    return f.fromByteArray(e.slice(r, t));
                }
            }
            function utf8Slice(e, r, t) {
                t = Math.min(e.length, t);
                var f = [];
                var n = r;
                while(n < t){
                    var i = e[n];
                    var o = null;
                    var u = i > 239 ? 4 : i > 223 ? 3 : i > 191 ? 2 : 1;
                    if (n + u <= t) {
                        var a, s, h, c;
                        switch(u){
                            case 1:
                                if (i < 128) {
                                    o = i;
                                }
                                break;
                            case 2:
                                a = e[n + 1];
                                if ((a & 192) === 128) {
                                    c = (i & 31) << 6 | a & 63;
                                    if (c > 127) {
                                        o = c;
                                    }
                                }
                                break;
                            case 3:
                                a = e[n + 1];
                                s = e[n + 2];
                                if ((a & 192) === 128 && (s & 192) === 128) {
                                    c = (i & 15) << 12 | (a & 63) << 6 | s & 63;
                                    if (c > 2047 && (c < 55296 || c > 57343)) {
                                        o = c;
                                    }
                                }
                                break;
                            case 4:
                                a = e[n + 1];
                                s = e[n + 2];
                                h = e[n + 3];
                                if ((a & 192) === 128 && (s & 192) === 128 && (h & 192) === 128) {
                                    c = (i & 15) << 18 | (a & 63) << 12 | (s & 63) << 6 | h & 63;
                                    if (c > 65535 && c < 1114112) {
                                        o = c;
                                    }
                                }
                        }
                    }
                    if (o === null) {
                        o = 65533;
                        u = 1;
                    } else if (o > 65535) {
                        o -= 65536;
                        f.push(o >>> 10 & 1023 | 55296);
                        o = 56320 | o & 1023;
                    }
                    f.push(o);
                    n += u;
                }
                return decodeCodePointsArray(f);
            }
            var u = 4096;
            function decodeCodePointsArray(e) {
                var r = e.length;
                if (r <= u) {
                    return String.fromCharCode.apply(String, e);
                }
                var t = "";
                var f = 0;
                while(f < r){
                    t += String.fromCharCode.apply(String, e.slice(f, f += u));
                }
                return t;
            }
            function asciiSlice(e, r, t) {
                var f = "";
                t = Math.min(e.length, t);
                for(var n = r; n < t; ++n){
                    f += String.fromCharCode(e[n] & 127);
                }
                return f;
            }
            function latin1Slice(e, r, t) {
                var f = "";
                t = Math.min(e.length, t);
                for(var n = r; n < t; ++n){
                    f += String.fromCharCode(e[n]);
                }
                return f;
            }
            function hexSlice(e, r, t) {
                var f = e.length;
                if (!r || r < 0) r = 0;
                if (!t || t < 0 || t > f) t = f;
                var n = "";
                for(var i = r; i < t; ++i){
                    n += s[e[i]];
                }
                return n;
            }
            function utf16leSlice(e, r, t) {
                var f = e.slice(r, t);
                var n = "";
                for(var i = 0; i < f.length; i += 2){
                    n += String.fromCharCode(f[i] + f[i + 1] * 256);
                }
                return n;
            }
            Buffer.prototype.slice = function slice(e, r) {
                var t = this.length;
                e = ~~e;
                r = r === undefined ? t : ~~r;
                if (e < 0) {
                    e += t;
                    if (e < 0) e = 0;
                } else if (e > t) {
                    e = t;
                }
                if (r < 0) {
                    r += t;
                    if (r < 0) r = 0;
                } else if (r > t) {
                    r = t;
                }
                if (r < e) r = e;
                var f = this.subarray(e, r);
                Object.setPrototypeOf(f, Buffer.prototype);
                return f;
            };
            function checkOffset(e, r, t) {
                if (e % 1 !== 0 || e < 0) throw new RangeError("offset is not uint");
                if (e + r > t) throw new RangeError("Trying to access beyond buffer length");
            }
            Buffer.prototype.readUIntLE = function readUIntLE(e, r, t) {
                e = e >>> 0;
                r = r >>> 0;
                if (!t) checkOffset(e, r, this.length);
                var f = this[e];
                var n = 1;
                var i = 0;
                while(++i < r && (n *= 256)){
                    f += this[e + i] * n;
                }
                return f;
            };
            Buffer.prototype.readUIntBE = function readUIntBE(e, r, t) {
                e = e >>> 0;
                r = r >>> 0;
                if (!t) {
                    checkOffset(e, r, this.length);
                }
                var f = this[e + --r];
                var n = 1;
                while(r > 0 && (n *= 256)){
                    f += this[e + --r] * n;
                }
                return f;
            };
            Buffer.prototype.readUInt8 = function readUInt8(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 1, this.length);
                return this[e];
            };
            Buffer.prototype.readUInt16LE = function readUInt16LE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 2, this.length);
                return this[e] | this[e + 1] << 8;
            };
            Buffer.prototype.readUInt16BE = function readUInt16BE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 2, this.length);
                return this[e] << 8 | this[e + 1];
            };
            Buffer.prototype.readUInt32LE = function readUInt32LE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return (this[e] | this[e + 1] << 8 | this[e + 2] << 16) + this[e + 3] * 16777216;
            };
            Buffer.prototype.readUInt32BE = function readUInt32BE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return this[e] * 16777216 + (this[e + 1] << 16 | this[e + 2] << 8 | this[e + 3]);
            };
            Buffer.prototype.readIntLE = function readIntLE(e, r, t) {
                e = e >>> 0;
                r = r >>> 0;
                if (!t) checkOffset(e, r, this.length);
                var f = this[e];
                var n = 1;
                var i = 0;
                while(++i < r && (n *= 256)){
                    f += this[e + i] * n;
                }
                n *= 128;
                if (f >= n) f -= Math.pow(2, 8 * r);
                return f;
            };
            Buffer.prototype.readIntBE = function readIntBE(e, r, t) {
                e = e >>> 0;
                r = r >>> 0;
                if (!t) checkOffset(e, r, this.length);
                var f = r;
                var n = 1;
                var i = this[e + --f];
                while(f > 0 && (n *= 256)){
                    i += this[e + --f] * n;
                }
                n *= 128;
                if (i >= n) i -= Math.pow(2, 8 * r);
                return i;
            };
            Buffer.prototype.readInt8 = function readInt8(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 1, this.length);
                if (!(this[e] & 128)) return this[e];
                return (255 - this[e] + 1) * -1;
            };
            Buffer.prototype.readInt16LE = function readInt16LE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 2, this.length);
                var t = this[e] | this[e + 1] << 8;
                return t & 32768 ? t | 4294901760 : t;
            };
            Buffer.prototype.readInt16BE = function readInt16BE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 2, this.length);
                var t = this[e + 1] | this[e] << 8;
                return t & 32768 ? t | 4294901760 : t;
            };
            Buffer.prototype.readInt32LE = function readInt32LE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return this[e] | this[e + 1] << 8 | this[e + 2] << 16 | this[e + 3] << 24;
            };
            Buffer.prototype.readInt32BE = function readInt32BE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return this[e] << 24 | this[e + 1] << 16 | this[e + 2] << 8 | this[e + 3];
            };
            Buffer.prototype.readFloatLE = function readFloatLE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return n.read(this, e, true, 23, 4);
            };
            Buffer.prototype.readFloatBE = function readFloatBE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 4, this.length);
                return n.read(this, e, false, 23, 4);
            };
            Buffer.prototype.readDoubleLE = function readDoubleLE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 8, this.length);
                return n.read(this, e, true, 52, 8);
            };
            Buffer.prototype.readDoubleBE = function readDoubleBE(e, r) {
                e = e >>> 0;
                if (!r) checkOffset(e, 8, this.length);
                return n.read(this, e, false, 52, 8);
            };
            function checkInt(e, r, t, f, n, i) {
                if (!Buffer.isBuffer(e)) throw new TypeError('"buffer" argument must be a Buffer instance');
                if (r > n || r < i) throw new RangeError('"value" argument is out of bounds');
                if (t + f > e.length) throw new RangeError("Index out of range");
            }
            Buffer.prototype.writeUIntLE = function writeUIntLE(e, r, t, f) {
                e = +e;
                r = r >>> 0;
                t = t >>> 0;
                if (!f) {
                    var n = Math.pow(2, 8 * t) - 1;
                    checkInt(this, e, r, t, n, 0);
                }
                var i = 1;
                var o = 0;
                this[r] = e & 255;
                while(++o < t && (i *= 256)){
                    this[r + o] = e / i & 255;
                }
                return r + t;
            };
            Buffer.prototype.writeUIntBE = function writeUIntBE(e, r, t, f) {
                e = +e;
                r = r >>> 0;
                t = t >>> 0;
                if (!f) {
                    var n = Math.pow(2, 8 * t) - 1;
                    checkInt(this, e, r, t, n, 0);
                }
                var i = t - 1;
                var o = 1;
                this[r + i] = e & 255;
                while(--i >= 0 && (o *= 256)){
                    this[r + i] = e / o & 255;
                }
                return r + t;
            };
            Buffer.prototype.writeUInt8 = function writeUInt8(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 1, 255, 0);
                this[r] = e & 255;
                return r + 1;
            };
            Buffer.prototype.writeUInt16LE = function writeUInt16LE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 2, 65535, 0);
                this[r] = e & 255;
                this[r + 1] = e >>> 8;
                return r + 2;
            };
            Buffer.prototype.writeUInt16BE = function writeUInt16BE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 2, 65535, 0);
                this[r] = e >>> 8;
                this[r + 1] = e & 255;
                return r + 2;
            };
            Buffer.prototype.writeUInt32LE = function writeUInt32LE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 4, 4294967295, 0);
                this[r + 3] = e >>> 24;
                this[r + 2] = e >>> 16;
                this[r + 1] = e >>> 8;
                this[r] = e & 255;
                return r + 4;
            };
            Buffer.prototype.writeUInt32BE = function writeUInt32BE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 4, 4294967295, 0);
                this[r] = e >>> 24;
                this[r + 1] = e >>> 16;
                this[r + 2] = e >>> 8;
                this[r + 3] = e & 255;
                return r + 4;
            };
            Buffer.prototype.writeIntLE = function writeIntLE(e, r, t, f) {
                e = +e;
                r = r >>> 0;
                if (!f) {
                    var n = Math.pow(2, 8 * t - 1);
                    checkInt(this, e, r, t, n - 1, -n);
                }
                var i = 0;
                var o = 1;
                var u = 0;
                this[r] = e & 255;
                while(++i < t && (o *= 256)){
                    if (e < 0 && u === 0 && this[r + i - 1] !== 0) {
                        u = 1;
                    }
                    this[r + i] = (e / o >> 0) - u & 255;
                }
                return r + t;
            };
            Buffer.prototype.writeIntBE = function writeIntBE(e, r, t, f) {
                e = +e;
                r = r >>> 0;
                if (!f) {
                    var n = Math.pow(2, 8 * t - 1);
                    checkInt(this, e, r, t, n - 1, -n);
                }
                var i = t - 1;
                var o = 1;
                var u = 0;
                this[r + i] = e & 255;
                while(--i >= 0 && (o *= 256)){
                    if (e < 0 && u === 0 && this[r + i + 1] !== 0) {
                        u = 1;
                    }
                    this[r + i] = (e / o >> 0) - u & 255;
                }
                return r + t;
            };
            Buffer.prototype.writeInt8 = function writeInt8(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 1, 127, -128);
                if (e < 0) e = 255 + e + 1;
                this[r] = e & 255;
                return r + 1;
            };
            Buffer.prototype.writeInt16LE = function writeInt16LE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 2, 32767, -32768);
                this[r] = e & 255;
                this[r + 1] = e >>> 8;
                return r + 2;
            };
            Buffer.prototype.writeInt16BE = function writeInt16BE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 2, 32767, -32768);
                this[r] = e >>> 8;
                this[r + 1] = e & 255;
                return r + 2;
            };
            Buffer.prototype.writeInt32LE = function writeInt32LE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 4, 2147483647, -2147483648);
                this[r] = e & 255;
                this[r + 1] = e >>> 8;
                this[r + 2] = e >>> 16;
                this[r + 3] = e >>> 24;
                return r + 4;
            };
            Buffer.prototype.writeInt32BE = function writeInt32BE(e, r, t) {
                e = +e;
                r = r >>> 0;
                if (!t) checkInt(this, e, r, 4, 2147483647, -2147483648);
                if (e < 0) e = 4294967295 + e + 1;
                this[r] = e >>> 24;
                this[r + 1] = e >>> 16;
                this[r + 2] = e >>> 8;
                this[r + 3] = e & 255;
                return r + 4;
            };
            function checkIEEE754(e, r, t, f, n, i) {
                if (t + f > e.length) throw new RangeError("Index out of range");
                if (t < 0) throw new RangeError("Index out of range");
            }
            function writeFloat(e, r, t, f, i) {
                r = +r;
                t = t >>> 0;
                if (!i) {
                    checkIEEE754(e, r, t, 4, 34028234663852886e22, -34028234663852886e22);
                }
                n.write(e, r, t, f, 23, 4);
                return t + 4;
            }
            Buffer.prototype.writeFloatLE = function writeFloatLE(e, r, t) {
                return writeFloat(this, e, r, true, t);
            };
            Buffer.prototype.writeFloatBE = function writeFloatBE(e, r, t) {
                return writeFloat(this, e, r, false, t);
            };
            function writeDouble(e, r, t, f, i) {
                r = +r;
                t = t >>> 0;
                if (!i) {
                    checkIEEE754(e, r, t, 8, 17976931348623157e292, -17976931348623157e292);
                }
                n.write(e, r, t, f, 52, 8);
                return t + 8;
            }
            Buffer.prototype.writeDoubleLE = function writeDoubleLE(e, r, t) {
                return writeDouble(this, e, r, true, t);
            };
            Buffer.prototype.writeDoubleBE = function writeDoubleBE(e, r, t) {
                return writeDouble(this, e, r, false, t);
            };
            Buffer.prototype.copy = function copy(e, r, t, f) {
                if (!Buffer.isBuffer(e)) throw new TypeError("argument should be a Buffer");
                if (!t) t = 0;
                if (!f && f !== 0) f = this.length;
                if (r >= e.length) r = e.length;
                if (!r) r = 0;
                if (f > 0 && f < t) f = t;
                if (f === t) return 0;
                if (e.length === 0 || this.length === 0) return 0;
                if (r < 0) {
                    throw new RangeError("targetStart out of bounds");
                }
                if (t < 0 || t >= this.length) throw new RangeError("Index out of range");
                if (f < 0) throw new RangeError("sourceEnd out of bounds");
                if (f > this.length) f = this.length;
                if (e.length - r < f - t) {
                    f = e.length - r + t;
                }
                var n = f - t;
                if (this === e && typeof Uint8Array.prototype.copyWithin === "function") {
                    this.copyWithin(r, t, f);
                } else if (this === e && t < r && r < f) {
                    for(var i = n - 1; i >= 0; --i){
                        e[i + r] = this[i + t];
                    }
                } else {
                    Uint8Array.prototype.set.call(e, this.subarray(t, f), r);
                }
                return n;
            };
            Buffer.prototype.fill = function fill(e, r, t, f) {
                if (typeof e === "string") {
                    if (typeof r === "string") {
                        f = r;
                        r = 0;
                        t = this.length;
                    } else if (typeof t === "string") {
                        f = t;
                        t = this.length;
                    }
                    if (f !== undefined && typeof f !== "string") {
                        throw new TypeError("encoding must be a string");
                    }
                    if (typeof f === "string" && !Buffer.isEncoding(f)) {
                        throw new TypeError("Unknown encoding: " + f);
                    }
                    if (e.length === 1) {
                        var n = e.charCodeAt(0);
                        if (f === "utf8" && n < 128 || f === "latin1") {
                            e = n;
                        }
                    }
                } else if (typeof e === "number") {
                    e = e & 255;
                } else if (typeof e === "boolean") {
                    e = Number(e);
                }
                if (r < 0 || this.length < r || this.length < t) {
                    throw new RangeError("Out of range index");
                }
                if (t <= r) {
                    return this;
                }
                r = r >>> 0;
                t = t === undefined ? this.length : t >>> 0;
                if (!e) e = 0;
                var i;
                if (typeof e === "number") {
                    for(i = r; i < t; ++i){
                        this[i] = e;
                    }
                } else {
                    var o = Buffer.isBuffer(e) ? e : Buffer.from(e, f);
                    var u = o.length;
                    if (u === 0) {
                        throw new TypeError('The value "' + e + '" is invalid for argument "value"');
                    }
                    for(i = 0; i < t - r; ++i){
                        this[i + r] = o[i % u];
                    }
                }
                return this;
            };
            var a = /[^+/0-9A-Za-z-_]/g;
            function base64clean(e) {
                e = e.split("=")[0];
                e = e.trim().replace(a, "");
                if (e.length < 2) return "";
                while(e.length % 4 !== 0){
                    e = e + "=";
                }
                return e;
            }
            function utf8ToBytes(e, r) {
                r = r || Infinity;
                var t;
                var f = e.length;
                var n = null;
                var i = [];
                for(var o = 0; o < f; ++o){
                    t = e.charCodeAt(o);
                    if (t > 55295 && t < 57344) {
                        if (!n) {
                            if (t > 56319) {
                                if ((r -= 3) > -1) i.push(239, 191, 189);
                                continue;
                            } else if (o + 1 === f) {
                                if ((r -= 3) > -1) i.push(239, 191, 189);
                                continue;
                            }
                            n = t;
                            continue;
                        }
                        if (t < 56320) {
                            if ((r -= 3) > -1) i.push(239, 191, 189);
                            n = t;
                            continue;
                        }
                        t = (n - 55296 << 10 | t - 56320) + 65536;
                    } else if (n) {
                        if ((r -= 3) > -1) i.push(239, 191, 189);
                    }
                    n = null;
                    if (t < 128) {
                        if ((r -= 1) < 0) break;
                        i.push(t);
                    } else if (t < 2048) {
                        if ((r -= 2) < 0) break;
                        i.push(t >> 6 | 192, t & 63 | 128);
                    } else if (t < 65536) {
                        if ((r -= 3) < 0) break;
                        i.push(t >> 12 | 224, t >> 6 & 63 | 128, t & 63 | 128);
                    } else if (t < 1114112) {
                        if ((r -= 4) < 0) break;
                        i.push(t >> 18 | 240, t >> 12 & 63 | 128, t >> 6 & 63 | 128, t & 63 | 128);
                    } else {
                        throw new Error("Invalid code point");
                    }
                }
                return i;
            }
            function asciiToBytes(e) {
                var r = [];
                for(var t = 0; t < e.length; ++t){
                    r.push(e.charCodeAt(t) & 255);
                }
                return r;
            }
            function utf16leToBytes(e, r) {
                var t, f, n;
                var i = [];
                for(var o = 0; o < e.length; ++o){
                    if ((r -= 2) < 0) break;
                    t = e.charCodeAt(o);
                    f = t >> 8;
                    n = t % 256;
                    i.push(n);
                    i.push(f);
                }
                return i;
            }
            function base64ToBytes(e) {
                return f.toByteArray(base64clean(e));
            }
            function blitBuffer(e, r, t, f) {
                for(var n = 0; n < f; ++n){
                    if (n + t >= r.length || n >= e.length) break;
                    r[n + t] = e[n];
                }
                return n;
            }
            function isInstance(e, r) {
                return e instanceof r || e != null && e.constructor != null && e.constructor.name != null && e.constructor.name === r.name;
            }
            function numberIsNaN(e) {
                return e !== e;
            }
            var s = function() {
                var e = "0123456789abcdef";
                var r = new Array(256);
                for(var t = 0; t < 16; ++t){
                    var f = t * 16;
                    for(var n = 0; n < 16; ++n){
                        r[f + n] = e[t] + e[n];
                    }
                }
                return r;
            }();
        },
        321: function(e, r) {
            /*! ieee754. BSD-3-Clause License. Feross Aboukhadijeh <https://feross.org/opensource> */ r.read = function(e, r, t, f, n) {
                var i, o;
                var u = n * 8 - f - 1;
                var a = (1 << u) - 1;
                var s = a >> 1;
                var h = -7;
                var c = t ? n - 1 : 0;
                var l = t ? -1 : 1;
                var p = e[r + c];
                c += l;
                i = p & (1 << -h) - 1;
                p >>= -h;
                h += u;
                for(; h > 0; i = i * 256 + e[r + c], c += l, h -= 8){}
                o = i & (1 << -h) - 1;
                i >>= -h;
                h += f;
                for(; h > 0; o = o * 256 + e[r + c], c += l, h -= 8){}
                if (i === 0) {
                    i = 1 - s;
                } else if (i === a) {
                    return o ? NaN : (p ? -1 : 1) * Infinity;
                } else {
                    o = o + Math.pow(2, f);
                    i = i - s;
                }
                return (p ? -1 : 1) * o * Math.pow(2, i - f);
            };
            r.write = function(e, r, t, f, n, i) {
                var o, u, a;
                var s = i * 8 - n - 1;
                var h = (1 << s) - 1;
                var c = h >> 1;
                var l = n === 23 ? Math.pow(2, -24) - Math.pow(2, -77) : 0;
                var p = f ? 0 : i - 1;
                var y = f ? 1 : -1;
                var g = r < 0 || r === 0 && 1 / r < 0 ? 1 : 0;
                r = Math.abs(r);
                if (isNaN(r) || r === Infinity) {
                    u = isNaN(r) ? 1 : 0;
                    o = h;
                } else {
                    o = Math.floor(Math.log(r) / Math.LN2);
                    if (r * (a = Math.pow(2, -o)) < 1) {
                        o--;
                        a *= 2;
                    }
                    if (o + c >= 1) {
                        r += l / a;
                    } else {
                        r += l * Math.pow(2, 1 - c);
                    }
                    if (r * a >= 2) {
                        o++;
                        a /= 2;
                    }
                    if (o + c >= h) {
                        u = 0;
                        o = h;
                    } else if (o + c >= 1) {
                        u = (r * a - 1) * Math.pow(2, n);
                        o = o + c;
                    } else {
                        u = r * Math.pow(2, c - 1) * Math.pow(2, n);
                        o = 0;
                    }
                }
                for(; n >= 8; e[t + p] = u & 255, p += y, u /= 256, n -= 8){}
                o = o << n | u;
                s += n;
                for(; s > 0; e[t + p] = o & 255, p += y, o /= 256, s -= 8){}
                e[t + p - y] |= g * 128;
            };
        }
    };
    var r = {};
    function __nccwpck_require__(t) {
        var f = r[t];
        if (f !== undefined) {
            return f.exports;
        }
        var n = r[t] = {
            exports: {}
        };
        var i = true;
        try {
            e[t](n, n.exports, __nccwpck_require__);
            i = false;
        } finally{
            if (i) delete r[t];
        }
        return n.exports;
    }
    if (typeof __nccwpck_require__ !== "undefined") __nccwpck_require__.ab = ("TURBOPACK compile-time value", "/ROOT/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/buffer") + "/";
    var t = __nccwpck_require__(230);
    module.exports = t;
})();
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/cjs/react-compiler-runtime.development.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * @license React
 * react-compiler-runtime.development.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ "use strict";
"production" !== ("TURBOPACK compile-time value", "development") && function() {
    var ReactSharedInternals = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)").__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
    exports.c = function(size) {
        var dispatcher = ReactSharedInternals.H;
        null === dispatcher && console.error("Invalid hook call. Hooks can only be called inside of the body of a function component. This could happen for one of the following reasons:\n1. You might have mismatching versions of React and the renderer (such as React DOM)\n2. You might be breaking the Rules of Hooks\n3. You might have more than one copy of React in the same app\nSee https://react.dev/link/invalid-hook-call for tips about how to debug and fix this problem.");
        return dispatcher.useMemoCache(size);
    };
}();
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ 'use strict';
if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
;
else {
    module.exports = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/cjs/react-compiler-runtime.development.js [app-client] (ecmascript)");
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/format-url.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
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
"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    formatUrl: null,
    formatWithValidation: null,
    urlObjectKeys: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    formatUrl: function() {
        return formatUrl;
    },
    formatWithValidation: function() {
        return formatWithValidation;
    },
    urlObjectKeys: function() {
        return urlObjectKeys;
    }
});
const _interop_require_wildcard = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/@swc/helpers/cjs/_interop_require_wildcard.cjs [app-client] (ecmascript)");
const _querystring = /*#__PURE__*/ _interop_require_wildcard._(__turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/querystring.js [app-client] (ecmascript)"));
const slashedProtocols = /https?|ftp|gopher|file/;
function formatUrl(urlObj) {
    let { auth, hostname } = urlObj;
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
        query = String(_querystring.urlQueryToSearchParams(query));
    }
    let search = urlObj.search || query && `?${query}` || '';
    if (protocol && !protocol.endsWith(':')) protocol += ':';
    if (urlObj.slashes || (!protocol || slashedProtocols.test(protocol)) && host !== false) {
        host = '//' + (host || '');
        if (pathname && pathname[0] !== '/') pathname = '/' + pathname;
    } else if (!host) {
        host = '';
    }
    if (hash && hash[0] !== '#') hash = '#' + hash;
    if (search && search[0] !== '?') search = '?' + search;
    pathname = pathname.replace(/[?#]/g, encodeURIComponent);
    search = search.replace('#', '%23');
    return `${protocol}${host}${pathname}${search}${hash}`;
}
const urlObjectKeys = [
    'auth',
    'hash',
    'host',
    'hostname',
    'href',
    'path',
    'pathname',
    'port',
    'protocol',
    'query',
    'search',
    'slashes'
];
function formatWithValidation(url) {
    if ("TURBOPACK compile-time truthy", 1) {
        if (url !== null && typeof url === 'object') {
            Object.keys(url).forEach((key)=>{
                if (!urlObjectKeys.includes(key)) {
                    console.warn(`Unknown key passed via urlObject into url.format: ${key}`);
                }
            });
        }
    }
    return formatUrl(url);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/is-local-url.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "isLocalURL", {
    enumerable: true,
    get: function() {
        return isLocalURL;
    }
});
const _utils = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils.js [app-client] (ecmascript)");
const _hasbasepath = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/has-base-path.js [app-client] (ecmascript)");
function isLocalURL(url) {
    // prevent a hydration mismatch on href for url with anchor refs
    if (!(0, _utils.isAbsoluteUrl)(url)) return true;
    try {
        // absolute urls can be local if they are on the same origin
        const locationOrigin = (0, _utils.getLocationOrigin)();
        const resolved = new URL(url, locationOrigin);
        return resolved.origin === locationOrigin && (0, _hasbasepath.hasBasePath)(resolved.pathname);
    } catch (_) {
        return false;
    }
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/router/utils/querystring.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    assign: null,
    searchParamsToUrlQuery: null,
    urlQueryToSearchParams: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    assign: function() {
        return assign;
    },
    searchParamsToUrlQuery: function() {
        return searchParamsToUrlQuery;
    },
    urlQueryToSearchParams: function() {
        return urlQueryToSearchParams;
    }
});
function searchParamsToUrlQuery(searchParams) {
    const query = {};
    for (const [key, value] of searchParams.entries()){
        const existing = query[key];
        if (typeof existing === 'undefined') {
            query[key] = value;
        } else if (Array.isArray(existing)) {
            existing.push(value);
        } else {
            query[key] = [
                existing,
                value
            ];
        }
    }
    return query;
}
function stringifyUrlQueryParam(param) {
    if (typeof param === 'string') {
        return param;
    }
    if (typeof param === 'number' && !isNaN(param) || typeof param === 'boolean') {
        return String(param);
    } else {
        return '';
    }
}
function urlQueryToSearchParams(query) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(query)){
        if (Array.isArray(value)) {
            for (const item of value){
                searchParams.append(key, stringifyUrlQueryParam(item));
            }
        } else {
            searchParams.set(key, stringifyUrlQueryParam(value));
        }
    }
    return searchParams;
}
function assign(target, ...searchParamsList) {
    for (const searchParams of searchParamsList){
        for (const key of searchParams.keys()){
            target.delete(key);
        }
        for (const [key, value] of searchParams.entries()){
            target.append(key, value);
        }
    }
    return target;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    DecodeError: null,
    MiddlewareNotFoundError: null,
    MissingStaticPage: null,
    NormalizeError: null,
    PageNotFoundError: null,
    SP: null,
    ST: null,
    WEB_VITALS: null,
    execOnce: null,
    getDisplayName: null,
    getLocationOrigin: null,
    getURL: null,
    isAbsoluteUrl: null,
    isResSent: null,
    loadGetInitialProps: null,
    normalizeRepeatedSlashes: null,
    stringifyError: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    DecodeError: function() {
        return DecodeError;
    },
    MiddlewareNotFoundError: function() {
        return MiddlewareNotFoundError;
    },
    MissingStaticPage: function() {
        return MissingStaticPage;
    },
    NormalizeError: function() {
        return NormalizeError;
    },
    PageNotFoundError: function() {
        return PageNotFoundError;
    },
    SP: function() {
        return SP;
    },
    ST: function() {
        return ST;
    },
    WEB_VITALS: function() {
        return WEB_VITALS;
    },
    execOnce: function() {
        return execOnce;
    },
    getDisplayName: function() {
        return getDisplayName;
    },
    getLocationOrigin: function() {
        return getLocationOrigin;
    },
    getURL: function() {
        return getURL;
    },
    isAbsoluteUrl: function() {
        return isAbsoluteUrl;
    },
    isResSent: function() {
        return isResSent;
    },
    loadGetInitialProps: function() {
        return loadGetInitialProps;
    },
    normalizeRepeatedSlashes: function() {
        return normalizeRepeatedSlashes;
    },
    stringifyError: function() {
        return stringifyError;
    }
});
const WEB_VITALS = [
    'CLS',
    'FCP',
    'FID',
    'INP',
    'LCP',
    'TTFB'
];
function execOnce(fn) {
    let used = false;
    let result;
    return (...args)=>{
        if (!used) {
            used = true;
            result = fn(...args);
        }
        return result;
    };
}
// Scheme: https://tools.ietf.org/html/rfc3986#section-3.1
// Absolute URL: https://tools.ietf.org/html/rfc3986#section-4.3
const ABSOLUTE_URL_REGEX = /^[a-zA-Z][a-zA-Z\d+\-.]*?:/;
const isAbsoluteUrl = (url)=>{
    // Fast path: an absolute URL must start with a letter (the scheme).
    // Check for a-z and A-Z without the cost of the regex.
    const c = url.charCodeAt(0);
    const isLetter = c >= 65 /* A */  && c <= 90 || c >= 97 /* a */  && c <= 122;
    /* z */ if (!isLetter) {
        return false;
    }
    return ABSOLUTE_URL_REGEX.test(url);
};
function getLocationOrigin() {
    const { protocol, hostname, port } = window.location;
    return `${protocol}//${hostname}${port ? ':' + port : ''}`;
}
function getURL() {
    const { href } = window.location;
    const origin = getLocationOrigin();
    return href.substring(origin.length);
}
function getDisplayName(Component) {
    return typeof Component === 'string' ? Component : Component.displayName || Component.name || 'Unknown';
}
function isResSent(res) {
    return res.finished || res.headersSent;
}
function normalizeRepeatedSlashes(url) {
    const urlParts = url.split('?');
    const urlNoQuery = urlParts[0];
    return urlNoQuery // first we replace any non-encoded backslashes with forward
    // then normalize repeated forward slashes
    .replace(/\\/g, '/').replace(/\/\/+/g, '/') + (urlParts[1] ? `?${urlParts.slice(1).join('?')}` : '');
}
async function loadGetInitialProps(App, ctx) {
    if ("TURBOPACK compile-time truthy", 1) {
        if (App.prototype?.getInitialProps) {
            const message = `"${getDisplayName(App)}.getInitialProps()" is defined as an instance method - visit https://nextjs.org/docs/messages/get-initial-props-as-an-instance-method for more information.`;
            throw Object.defineProperty(new Error(message), "__NEXT_ERROR_CODE", {
                value: "E1035",
                enumerable: false,
                configurable: true
            });
        }
    }
    // when called from _app `ctx` is nested in `ctx`
    const res = ctx.res || ctx.ctx && ctx.ctx.res;
    if (!App.getInitialProps) {
        if (ctx.ctx && ctx.Component) {
            // @ts-ignore pageProps default
            return {
                pageProps: await loadGetInitialProps(ctx.Component, ctx.ctx)
            };
        }
        return {};
    }
    const props = await App.getInitialProps(ctx);
    if (res && isResSent(res)) {
        return props;
    }
    if (!props) {
        const message = `"${getDisplayName(App)}.getInitialProps()" should resolve to an object. But found "${props}" instead.`;
        throw Object.defineProperty(new Error(message), "__NEXT_ERROR_CODE", {
            value: "E1025",
            enumerable: false,
            configurable: true
        });
    }
    if ("TURBOPACK compile-time truthy", 1) {
        if (Object.keys(props).length === 0 && !ctx.ctx) {
            console.warn(`${getDisplayName(App)} returned an empty object from \`getInitialProps\`. This de-optimizes and prevents automatic static optimization. https://nextjs.org/docs/messages/empty-object-getInitialProps`);
        }
    }
    return props;
}
const SP = typeof performance !== 'undefined';
const ST = SP && [
    'mark',
    'measure',
    'getEntriesByName'
].every((method)=>typeof performance[method] === 'function');
class DecodeError extends Error {
}
class NormalizeError extends Error {
}
class PageNotFoundError extends Error {
    constructor(page){
        super();
        this.code = 'ENOENT';
        this.name = 'PageNotFoundError';
        this.message = `Cannot find module for page: ${page}`;
    }
}
class MissingStaticPage extends Error {
    constructor(page, message){
        super();
        this.message = `Failed to load static file for page: ${page} ${message}`;
    }
}
class MiddlewareNotFoundError extends Error {
    constructor(){
        super();
        this.code = 'ENOENT';
        this.message = `Cannot find the middleware module`;
    }
}
function stringifyError(error) {
    return JSON.stringify({
        message: error.message,
        stack: error.stack
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/shared/lib/utils/error-once.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "errorOnce", {
    enumerable: true,
    get: function() {
        return errorOnce;
    }
});
let errorOnce = (_)=>{};
if ("TURBOPACK compile-time truthy", 1) {
    const errors = new Set();
    errorOnce = (msg)=>{
        if (!errors.has(msg)) {
            console.error(msg);
        }
        errors.add(msg);
    };
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

module.exports = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/client/components/navigation.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/auth/defaultAccess.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "defaultAccess",
    ()=>defaultAccess
]);
const defaultAccess = ({ req: { user } })=>Boolean(user);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/collections/config/defaults.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "addDefaultsToAuthConfig",
    ()=>addDefaultsToAuthConfig,
    "addDefaultsToCollectionConfig",
    ()=>addDefaultsToCollectionConfig,
    "addDefaultsToLoginWithUsernameConfig",
    ()=>addDefaultsToLoginWithUsernameConfig,
    "authDefaults",
    ()=>authDefaults,
    "defaults",
    ()=>defaults,
    "loginWithUsernameDefaults",
    ()=>loginWithUsernameDefaults
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/auth/defaultAccess.js [app-client] (ecmascript)");
;
const defaults = {
    access: {
        create: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        read: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        unlock: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        update: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"]
    },
    admin: {
        components: {},
        custom: {},
        enableRichTextLink: true,
        enableRichTextRelationship: true,
        pagination: {
            defaultLimit: 10,
            limits: [
                5,
                10,
                25,
                50,
                100
            ]
        },
        useAsTitle: 'id'
    },
    auth: false,
    custom: {},
    endpoints: [],
    fields: [],
    hooks: {
        afterChange: [],
        afterDelete: [],
        afterForgotPassword: [],
        afterLogin: [],
        afterLogout: [],
        afterMe: [],
        afterOperation: [],
        afterRead: [],
        afterRefresh: [],
        beforeChange: [],
        beforeDelete: [],
        beforeLogin: [],
        beforeOperation: [],
        beforeRead: [],
        beforeValidate: [],
        me: [],
        refresh: []
    },
    indexes: [],
    timestamps: true,
    upload: false,
    versions: false
};
const addDefaultsToCollectionConfig = (collection)=>{
    collection.access = {
        create: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        delete: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        read: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        unlock: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        update: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$defaultAccess$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaultAccess"],
        ...collection.access || {}
    };
    collection.admin = {
        components: {},
        custom: {},
        enableRichTextLink: true,
        enableRichTextRelationship: true,
        useAsTitle: 'id',
        ...collection.admin || {},
        pagination: {
            defaultLimit: 10,
            limits: [
                5,
                10,
                25,
                50,
                100
            ],
            ...collection.admin?.pagination || {}
        }
    };
    collection.auth = collection.auth ?? false;
    collection.custom = collection.custom ?? {};
    collection.endpoints = collection.endpoints ?? [];
    collection.fields = collection.fields ?? [];
    collection.folders = collection.folders ?? false;
    collection.hooks = {
        afterChange: [],
        afterDelete: [],
        afterForgotPassword: [],
        afterLogin: [],
        afterLogout: [],
        afterMe: [],
        afterOperation: [],
        afterRead: [],
        afterRefresh: [],
        beforeChange: [],
        beforeDelete: [],
        beforeLogin: [],
        beforeOperation: [],
        beforeRead: [],
        beforeValidate: [],
        me: [],
        refresh: [],
        ...collection.hooks || {}
    };
    collection.timestamps = collection.timestamps ?? true;
    collection.upload = collection.upload ?? false;
    collection.versions = collection.versions ?? false;
    collection.indexes = collection.indexes ?? [];
    return collection;
};
const authDefaults = {
    cookies: {
        sameSite: 'Lax',
        secure: false
    },
    forgotPassword: {},
    lockTime: 600000,
    loginWithUsername: false,
    maxLoginAttempts: 5,
    tokenExpiration: 7200,
    useSessions: true,
    verify: false
};
const addDefaultsToAuthConfig = (auth)=>{
    auth.cookies = {
        sameSite: 'Lax',
        secure: false,
        ...auth.cookies || {}
    };
    auth.forgotPassword = auth.forgotPassword ?? {};
    auth.lockTime = auth.lockTime ?? 600000; // 10 minutes
    auth.loginWithUsername = auth.loginWithUsername ?? false;
    auth.maxLoginAttempts = auth.maxLoginAttempts ?? 5;
    auth.tokenExpiration = auth.tokenExpiration ?? 7200;
    auth.useSessions = auth.useSessions ?? true;
    auth.verify = auth.verify ?? false;
    auth.strategies = auth.strategies ?? [];
    if (!auth.disableLocalStrategy && auth.verify === true) {
        auth.verify = {};
    }
    return auth;
};
const loginWithUsernameDefaults = {
    allowEmailLogin: false,
    requireEmail: false,
    requireUsername: true
};
const addDefaultsToLoginWithUsernameConfig = (loginWithUsername)=>({
        allowEmailLogin: false,
        requireEmail: false,
        requireUsername: true,
        ...loginWithUsername || {}
    });
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/collections/config/defaults.js [app-client] (ecmascript) <export defaults as collectionDefaults>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "collectionDefaults",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$collections$2f$config$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["defaults"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$collections$2f$config$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/collections/config/defaults.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/config/types.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "serverProps",
    ()=>serverProps
]);
const serverProps = [
    'payload',
    'i18n',
    'locale',
    'params',
    'permissions',
    'searchParams',
    'permissions'
];
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/config/types.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/* eslint-disable @typescript-eslint/no-explicit-any */ __turbopack_context__.s([
    "fieldAffectsData",
    ()=>fieldAffectsData,
    "fieldHasMaxDepth",
    ()=>fieldHasMaxDepth,
    "fieldHasSubFields",
    ()=>fieldHasSubFields,
    "fieldIsArrayType",
    ()=>fieldIsArrayType,
    "fieldIsBlockType",
    ()=>fieldIsBlockType,
    "fieldIsGroupType",
    ()=>fieldIsGroupType,
    "fieldIsHiddenOrDisabled",
    ()=>fieldIsHiddenOrDisabled,
    "fieldIsID",
    ()=>fieldIsID,
    "fieldIsLocalized",
    ()=>fieldIsLocalized,
    "fieldIsPresentationalOnly",
    ()=>fieldIsPresentationalOnly,
    "fieldIsSidebar",
    ()=>fieldIsSidebar,
    "fieldIsVirtual",
    ()=>fieldIsVirtual,
    "fieldShouldBeLocalized",
    ()=>fieldShouldBeLocalized,
    "fieldSupportsMany",
    ()=>fieldSupportsMany,
    "groupHasName",
    ()=>groupHasName,
    "optionIsObject",
    ()=>optionIsObject,
    "optionIsValue",
    ()=>optionIsValue,
    "optionsAreObjects",
    ()=>optionsAreObjects,
    "tabHasName",
    ()=>tabHasName,
    "valueIsValueWithRelation",
    ()=>valueIsValueWithRelation
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
function valueIsValueWithRelation(value) {
    return value !== null && typeof value === 'object' && 'relationTo' in value && 'value' in value;
}
function fieldHasSubFields(field) {
    return field.type === 'group' || field.type === 'array' || field.type === 'row' || field.type === 'collapsible';
}
function fieldIsArrayType(field) {
    return field.type === 'array';
}
function fieldIsBlockType(field) {
    return field.type === 'blocks';
}
function fieldIsGroupType(field) {
    return field.type === 'group';
}
function optionIsObject(option) {
    return typeof option === 'object';
}
function optionsAreObjects(options) {
    return Array.isArray(options) && typeof options?.[0] === 'object';
}
function optionIsValue(option) {
    return typeof option === 'string';
}
function fieldSupportsMany(field) {
    return field.type === 'select' || field.type === 'relationship' || field.type === 'upload';
}
function fieldHasMaxDepth(field) {
    return (field.type === 'upload' || field.type === 'relationship' || field.type === 'join') && typeof field.maxDepth === 'number';
}
function fieldIsPresentationalOnly(field) {
    return field.type === 'ui';
}
function fieldIsSidebar(field) {
    return 'admin' in field && 'position' in field.admin && field.admin.position === 'sidebar';
}
function fieldIsID(field) {
    return 'name' in field && field.name === 'id';
}
function fieldIsHiddenOrDisabled(field) {
    return 'hidden' in field && field.hidden || 'admin' in field && 'disabled' in field.admin && field.admin.disabled;
}
function fieldAffectsData(field) {
    return 'name' in field && !fieldIsPresentationalOnly(field);
}
function tabHasName(tab) {
    return 'name' in tab;
}
function groupHasName(group) {
    return 'name' in group;
}
function fieldIsLocalized(field) {
    return 'localized' in field && field.localized;
}
function fieldShouldBeLocalized({ field, parentIsLocalized }) {
    return Boolean('localized' in field && field.localized && (!parentIsLocalized || __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].env.NEXT_PUBLIC_PAYLOAD_COMPATIBILITY_allowLocalizedWithinLocalized === 'true'));
}
function fieldIsVirtual(field) {
    return 'virtual' in field && Boolean(field.virtual);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/getFieldPaths.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getFieldPaths",
    ()=>getFieldPaths
]);
function getFieldPaths({ field, index, parentIndexPath, parentPath = '', parentSchemaPath }) {
    const parentPathSegments = parentPath.split('.');
    const parentPathIsUnnamed = parentPathSegments?.[parentPathSegments.length - 1]?.startsWith('_index-');
    const parentWithoutIndex = parentPathIsUnnamed ? parentPathSegments.slice(0, -1).join('.') : parentPath;
    const parentPathToUse = parentPathIsUnnamed ? parentWithoutIndex : parentPath;
    if ('name' in field) {
        return {
            indexPath: '',
            path: `${parentPathToUse ? parentPathToUse + '.' : ''}${field.name}`,
            schemaPath: `${parentSchemaPath ? parentSchemaPath + '.' : ''}${field.name}`
        };
    }
    const indexSuffix = `_index-${`${parentIndexPath ? parentIndexPath + '-' : ''}${index}`}`;
    const parentSchemaPathSegments = parentSchemaPath.split('.');
    const parentSchemaPathIsUnnamed = parentSchemaPathSegments?.[parentSchemaPathSegments.length - 1]?.startsWith('_index-');
    return {
        indexPath: `${parentIndexPath ? parentIndexPath + '-' : ''}${index}`,
        path: `${parentPathToUse ? parentPathToUse + '.' : ''}${indexSuffix}`,
        schemaPath: parentSchemaPathIsUnnamed ? `${parentSchemaPath}-${index}` : `${parentSchemaPath ? parentSchemaPath + '.' : ''}${indexSuffix}`
    };
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/validations.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "array",
    ()=>array,
    "blocks",
    ()=>blocks,
    "checkbox",
    ()=>checkbox,
    "code",
    ()=>code,
    "confirmPassword",
    ()=>confirmPassword,
    "date",
    ()=>date,
    "email",
    ()=>email,
    "json",
    ()=>json,
    "number",
    ()=>number,
    "password",
    ()=>password,
    "point",
    ()=>point,
    "radio",
    ()=>radio,
    "relationship",
    ()=>relationship,
    "richText",
    ()=>richText,
    "select",
    ()=>select,
    "text",
    ()=>text,
    "textarea",
    ()=>textarea,
    "upload",
    ()=>upload,
    "username",
    ()=>username,
    "validateBlocksFilterOptions",
    ()=>validateBlocksFilterOptions,
    "validations",
    ()=>validations
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$ajv$2f$dist$2f$ajv$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/ajv/dist/ajv.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isNumber$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/isNumber.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isValidID$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/isValidID.js [app-client] (ecmascript)");
;
;
const ObjectId = 'default' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"] ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].default : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
;
;
const text = (value, { hasMany, maxLength: fieldMaxLength, maxRows, minLength, minRows, req: { payload: { config }, t }, required })=>{
    let maxLength;
    if (!required) {
        if (value === undefined || value === null) {
            return true;
        }
    }
    if (hasMany === true) {
        const lengthValidationResult = validateArrayLength(value, {
            maxRows,
            minRows,
            required,
            t
        });
        if (typeof lengthValidationResult === 'string') {
            return lengthValidationResult;
        }
    }
    if (typeof config?.defaultMaxTextLength === 'number') {
        maxLength = config.defaultMaxTextLength;
    }
    if (typeof fieldMaxLength === 'number') {
        maxLength = fieldMaxLength;
    }
    const stringsToValidate = Array.isArray(value) ? value : [
        value
    ];
    for (const stringValue of stringsToValidate){
        const length = stringValue?.length || 0;
        if (typeof maxLength === 'number' && length > maxLength) {
            return t('validation:shorterThanMax', {
                label: t('general:value'),
                maxLength,
                stringValue
            });
        }
        if (typeof minLength === 'number' && length < minLength) {
            return t('validation:longerThanMin', {
                label: t('general:value'),
                minLength,
                stringValue
            });
        }
    }
    if (required) {
        if (!value || (typeof value === 'string' || Array.isArray(value)) && value.length === 0) {
            return t('validation:required');
        }
    }
    return true;
};
const password = (value, { maxLength: fieldMaxLength, minLength = 3, req: { payload: { config }, t }, required })=>{
    let maxLength;
    if (typeof config?.defaultMaxTextLength === 'number') {
        maxLength = config.defaultMaxTextLength;
    }
    if (typeof fieldMaxLength === 'number') {
        maxLength = fieldMaxLength;
    }
    if (value && maxLength && value.length > maxLength) {
        return t('validation:shorterThanMax', {
            maxLength
        });
    }
    if (value && minLength && value.length < minLength) {
        return t('validation:longerThanMin', {
            minLength
        });
    }
    if (required && !value) {
        return t('validation:required');
    }
    return true;
};
const confirmPassword = (value, { req: { t }, required, siblingData })=>{
    if (required && !value) {
        return t('validation:required');
    }
    if (value && value !== siblingData.password) {
        return t('fields:passwordsDoNotMatch');
    }
    return true;
};
const email = (value, { collectionSlug, req: { payload: { collections, config }, t }, required, siblingData })=>{
    if (collectionSlug) {
        const collection = collections?.[collectionSlug]?.config ?? config.collections.find(({ slug })=>slug === collectionSlug) // If this is run on the client, `collections` will be undefined, but `config.collections` will be available
        ;
        if (collection.auth.loginWithUsername && !collection.auth.loginWithUsername?.requireUsername && !collection.auth.loginWithUsername?.requireEmail) {
            if (!value && !siblingData?.username) {
                return t('validation:required');
            }
        }
    }
    /**
   * Disallows emails with double quotes (e.g., "user"@example.com, user@"example.com", "user@example.com")
   * Rejects spaces anywhere in the email (e.g., user @example.com, user@ example.com, user name@example.com)
   * Prevents consecutive dots in the local or domain part (e.g., user..name@example.com, user@example..com)
   * Disallows domains that start or end with a hyphen (e.g., user@-example.com, user@example-.com)
   * Allows standard email formats (e.g., user@example.com, user.name+alias@example.co.uk, user-name@example.org)
   * Allows domains with consecutive hyphens as long as they are not leading/trailing (e.g., user@ex--ample.com)
   * Supports multiple subdomains (e.g., user@sub.domain.example.com)
   */ const emailRegex = /^(?!.*\.\.)[\w!#$%&'*+/=?^`{|}~-](?:[\w!#$%&'*+/=?^`{|}~.-]*[\w!#$%&'*+/=?^`{|}~-])?@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,}$/i;
    if (value && !emailRegex.test(value) || !value && required) {
        return t('validation:emailAddress');
    }
    return true;
};
const username = (value, { collectionSlug, req: { payload: { collections, config }, t }, required, siblingData })=>{
    let maxLength;
    if (collectionSlug) {
        const collection = collections?.[collectionSlug]?.config ?? config.collections.find(({ slug })=>slug === collectionSlug) // If this is run on the client, `collections` will be undefined, but `config.collections` will be available
        ;
        if (collection.auth.loginWithUsername && !collection.auth.loginWithUsername?.requireUsername && !collection.auth.loginWithUsername?.requireEmail) {
            if (!value && !siblingData?.email) {
                return t('validation:required');
            }
        }
    }
    if (typeof config?.defaultMaxTextLength === 'number') {
        maxLength = config.defaultMaxTextLength;
    }
    if (value && maxLength && value.length > maxLength) {
        return t('validation:shorterThanMax', {
            maxLength
        });
    }
    if (!value && required) {
        return t('validation:required');
    }
    return true;
};
const textarea = (value, { maxLength: fieldMaxLength, minLength, req: { payload: { config }, t }, required })=>{
    let maxLength;
    if (typeof config?.defaultMaxTextLength === 'number') {
        maxLength = config.defaultMaxTextLength;
    }
    if (typeof fieldMaxLength === 'number') {
        maxLength = fieldMaxLength;
    }
    if (value && maxLength && value.length > maxLength) {
        return t('validation:shorterThanMax', {
            maxLength
        });
    }
    if (value && minLength && value.length < minLength) {
        return t('validation:longerThanMin', {
            minLength
        });
    }
    if (required && !value) {
        return t('validation:required');
    }
    return true;
};
const code = (value, { req: { t }, required })=>{
    if (required && value === undefined) {
        return t('validation:required');
    }
    return true;
};
const json = (value, { jsonError, jsonSchema, req: { t }, required })=>{
    const isNotEmpty = (value)=>{
        if (value === undefined || value === null) {
            return false;
        }
        if (Array.isArray(value) && value.length === 0) {
            return false;
        }
        if (typeof value === 'object' && Object.keys(value).length === 0) {
            return false;
        }
        return true;
    };
    const fetchSchema = ({ schema, uri })=>{
        if (uri && schema) {
            return schema;
        }
        return fetch(uri).then((response)=>{
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        }).then((_json)=>{
            const json = _json;
            const jsonSchemaSanitizations = {
                id: undefined,
                $id: json.id,
                $schema: 'http://json-schema.org/draft-07/schema#'
            };
            return Object.assign(json, jsonSchemaSanitizations);
        });
    };
    if (required && !value) {
        return t('validation:required');
    }
    if (jsonError !== undefined) {
        return t('validation:invalidInput');
    }
    if (jsonSchema && isNotEmpty(value)) {
        try {
            jsonSchema.schema = fetchSchema(jsonSchema);
            const { schema } = jsonSchema;
            // @ts-expect-error missing types
            const ajv = new __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$ajv$2f$dist$2f$ajv$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]();
            if (!ajv.validate(schema, value)) {
                return ajv.errorsText();
            }
        } catch (error) {
            return error instanceof Error ? error.message : 'Unknown error';
        }
    }
    return true;
};
const checkbox = (value, { req: { t }, required })=>{
    if (value && typeof value !== 'boolean' || required && typeof value !== 'boolean') {
        return t('validation:trueOrFalse');
    }
    return true;
};
const date = (value, { name, req: { t }, required, siblingData, timezone })=>{
    const validDate = value && !isNaN(Date.parse(value.toString()));
    // We need to also check for the timezone data based on this field's config
    // We cannot do this inside the timezone field validation as it's visually hidden
    const hasRequiredTimezone = timezone && required;
    const selectedTimezone = siblingData?.[`${name}_tz`];
    // Always resolve to true if the field is not required, as timezone may be optional too then
    const validTimezone = hasRequiredTimezone ? Boolean(selectedTimezone) : true;
    if (validDate && validTimezone) {
        return true;
    }
    if (validDate && !validTimezone) {
        return t('validation:timezoneRequired');
    }
    if (value) {
        return t('validation:notValidDate', {
            value
        });
    }
    if (required) {
        return t('validation:required');
    }
    return true;
};
const richText = async (value, options)=>{
    if (!options?.editor) {
        throw new Error('richText field has no editor property.');
    }
    if (typeof options?.editor === 'function') {
        throw new Error('Attempted to access unsanitized rich text editor.');
    }
    const editor = options?.editor;
    return editor.validate(value, options);
};
const validateArrayLength = (value, options)=>{
    const { maxRows, minRows, required, t } = options;
    const arrayLength = Array.isArray(value) ? value.length : value || 0;
    if (!required && arrayLength === 0) {
        return true;
    }
    if (minRows && arrayLength < minRows) {
        return t('validation:requiresAtLeast', {
            count: minRows,
            label: t('general:rows')
        });
    }
    if (maxRows && arrayLength > maxRows) {
        return t('validation:requiresNoMoreThan', {
            count: maxRows,
            label: t('general:rows')
        });
    }
    if (required && !arrayLength) {
        return t('validation:requiresAtLeast', {
            count: 1,
            label: t('general:row')
        });
    }
    return true;
};
const number = (value, { hasMany, max, maxRows, min, minRows, req: { t }, required })=>{
    if (hasMany === true) {
        const lengthValidationResult = validateArrayLength(value, {
            maxRows,
            minRows,
            required,
            t
        });
        if (typeof lengthValidationResult === 'string') {
            return lengthValidationResult;
        }
    }
    if (!value && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isNumber$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(value)) {
        // if no value is present, validate based on required
        if (required) {
            return t('validation:required');
        }
        if (!required) {
            return true;
        }
    }
    const numbersToValidate = Array.isArray(value) ? value : [
        value
    ];
    for (const number of numbersToValidate){
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isNumber$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isNumber"])(number)) {
            return t('validation:enterNumber');
        }
        const numberValue = parseFloat(number);
        if (typeof max === 'number' && numberValue > max) {
            return t('validation:greaterThanMax', {
                label: t('general:value'),
                max,
                value
            });
        }
        if (typeof min === 'number' && numberValue < min) {
            return t('validation:lessThanMin', {
                label: t('general:value'),
                min,
                value
            });
        }
    }
    return true;
};
const array = (value, { maxRows, minRows, req: { t }, required })=>{
    return validateArrayLength(value, {
        maxRows,
        minRows,
        required,
        t
    });
};
async function validateBlocksFilterOptions({ id, data, filterOptions, req, siblingData, value }) {
    const allBlockSlugs = Array.isArray(value) ? value.map((b)=>b.blockType).filter((s)=>Boolean(s)) : [];
    // if undefined => all blocks allowed
    let allowedBlockSlugs = undefined;
    if (typeof filterOptions === 'function') {
        const result = await filterOptions({
            id: id,
            data,
            req,
            siblingData,
            user: req.user
        });
        if (result !== true && Array.isArray(result)) {
            allowedBlockSlugs = result;
        }
    } else if (Array.isArray(filterOptions)) {
        allowedBlockSlugs = filterOptions;
    }
    const invalidBlockSlugs = [];
    if (allowedBlockSlugs) {
        for (const blockSlug of allBlockSlugs){
            if (!allowedBlockSlugs.includes(blockSlug)) {
                invalidBlockSlugs.push(blockSlug);
            }
        }
    }
    return {
        allBlockSlugs,
        allowedBlockSlugs,
        invalidBlockSlugs
    };
}
const blocks = async (value, { id, data, filterOptions, maxRows, minRows, req: { t }, req, required, siblingData })=>{
    const lengthValidationResult = validateArrayLength(value, {
        maxRows,
        minRows,
        required,
        t
    });
    if (typeof lengthValidationResult === 'string') {
        return lengthValidationResult;
    }
    if (filterOptions) {
        const { invalidBlockSlugs } = await validateBlocksFilterOptions({
            id,
            data,
            filterOptions,
            req,
            siblingData,
            value
        });
        if (invalidBlockSlugs?.length) {
            return t('validation:invalidBlocks', {
                blocks: invalidBlockSlugs.join(', ')
            });
        }
    }
    return true;
};
const validateFilterOptions = async (value, { id, blockData, data, filterOptions, relationTo, req, req: { t, user }, siblingData })=>{
    if (typeof filterOptions !== 'undefined' && value) {
        const options = {};
        const falseCollections = [];
        const collections = !Array.isArray(relationTo) ? [
            relationTo
        ] : relationTo;
        const values = Array.isArray(value) ? value : [
            value
        ];
        for (const collection of collections){
            try {
                let optionFilter = typeof filterOptions === 'function' ? await filterOptions({
                    id: id,
                    blockData,
                    data,
                    relationTo: collection,
                    req,
                    siblingData,
                    user
                }) : filterOptions;
                if (optionFilter === true) {
                    optionFilter = null;
                }
                const valueIDs = [];
                values.forEach((val)=>{
                    if (typeof val === 'object') {
                        if (val?.value) {
                            valueIDs.push(val.value);
                        } else if (ObjectId.isValid(val)) {
                            valueIDs.push(new ObjectId(val).toHexString());
                        }
                    }
                    if (typeof val === 'string' || typeof val === 'number') {
                        valueIDs.push(val);
                    }
                });
                if (valueIDs.length > 0) {
                    const findWhere = {
                        and: [
                            {
                                id: {
                                    in: valueIDs
                                }
                            }
                        ]
                    };
                    // @ts-expect-error - I don't understand why optionFilter is inferred as `false | Where | null` instead of `boolean | Where | null`
                    if (optionFilter && optionFilter !== true) {
                        findWhere.and?.push(optionFilter);
                    }
                    if (optionFilter === false) {
                        falseCollections.push(collection);
                    }
                    const result = await req.payloadDataLoader.find({
                        collection,
                        depth: 0,
                        limit: 0,
                        pagination: false,
                        req,
                        where: findWhere
                    });
                    options[collection] = result.docs.map((doc)=>doc.id);
                } else {
                    options[collection] = [];
                }
            } catch (err) {
                req.payload.logger.error({
                    err,
                    msg: `Error validating filter options for collection ${collection}`
                });
                options[collection] = [];
            }
        }
        const invalidRelationships = values.filter((val)=>{
            let collection;
            let requestedID;
            if (typeof relationTo === 'string') {
                collection = relationTo;
                if (typeof val === 'string' || typeof val === 'number') {
                    requestedID = val;
                }
                if (typeof val === 'object' && ObjectId.isValid(val)) {
                    requestedID = new ObjectId(val).toHexString();
                }
            }
            if (Array.isArray(relationTo) && typeof val === 'object' && val?.relationTo) {
                collection = val.relationTo;
                requestedID = val.value;
            }
            if (falseCollections.find((slug)=>relationTo === slug)) {
                return true;
            }
            if (!options[collection]) {
                return true;
            }
            return options[collection].indexOf(requestedID) === -1;
        });
        if (invalidRelationships.length > 0) {
            return invalidRelationships.reduce((err, invalid, i)=>{
                return `${err} ${JSON.stringify(invalid)}${invalidRelationships.length === i + 1 ? ',' : ''} `;
            }, t('validation:invalidSelections'));
        }
        return true;
    }
    return true;
};
const upload = async (value, options)=>{
    const { event, maxRows, minRows, relationTo, req: { payload, t }, required } = options;
    if ((!value && typeof value !== 'number' || Array.isArray(value) && value.length === 0) && required) {
        return t('validation:required');
    }
    if (Array.isArray(value) && value.length > 0) {
        if (minRows && value.length < minRows) {
            return t('validation:lessThanMin', {
                label: t('general:rows'),
                min: minRows,
                value: value.length
            });
        }
        if (maxRows && value.length > maxRows) {
            return t('validation:greaterThanMax', {
                label: t('general:rows'),
                max: maxRows,
                value: value.length
            });
        }
    }
    if (typeof value !== 'undefined' && value !== null) {
        const values = Array.isArray(value) ? value : [
            value
        ];
        const invalidRelationships = values.filter((val)=>{
            let collectionSlug;
            let requestedID;
            if (typeof relationTo === 'string') {
                collectionSlug = relationTo;
                // custom id
                if (val || typeof val === 'number') {
                    requestedID = val;
                }
            }
            if (Array.isArray(relationTo) && typeof val === 'object' && val?.relationTo) {
                collectionSlug = val.relationTo;
                requestedID = val.value;
            }
            if (requestedID === null) {
                return false;
            }
            const idType = payload.collections[collectionSlug]?.customIDType || payload?.db?.defaultIDType || 'text';
            return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isValidID$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidID"])(requestedID, idType);
        });
        if (invalidRelationships.length > 0) {
            return `This relationship field has the following invalid relationships: ${invalidRelationships.map((err, invalid)=>{
                return `${err} ${JSON.stringify(invalid)}`;
            }).join(', ')}`;
        }
    }
    if (event === 'onChange') {
        return true;
    }
    return validateFilterOptions(value, options);
};
const relationship = async (value, options)=>{
    const { event, maxRows, minRows, relationTo, req: { payload, t }, required } = options;
    if ((!value && typeof value !== 'number' || Array.isArray(value) && value.length === 0) && required) {
        return t('validation:required');
    }
    if (Array.isArray(value) && value.length > 0) {
        if (minRows && value.length < minRows) {
            return t('validation:lessThanMin', {
                label: t('general:rows'),
                min: minRows,
                value: value.length
            });
        }
        if (maxRows && value.length > maxRows) {
            return t('validation:greaterThanMax', {
                label: t('general:rows'),
                max: maxRows,
                value: value.length
            });
        }
    }
    if (typeof value !== 'undefined' && value !== null) {
        const values = Array.isArray(value) ? value : [
            value
        ];
        const invalidRelationships = values.filter((val)=>{
            let collectionSlug;
            let requestedID;
            if (typeof relationTo === 'string') {
                collectionSlug = relationTo;
                // custom id
                if (val || typeof val === 'number') {
                    requestedID = val;
                }
            }
            if (Array.isArray(relationTo) && typeof val === 'object' && val?.relationTo) {
                collectionSlug = val.relationTo;
                requestedID = val.value;
            }
            if (requestedID === null) {
                return false;
            }
            const idType = payload.collections[collectionSlug]?.customIDType || payload?.db?.defaultIDType || 'text';
            return !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$isValidID$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isValidID"])(requestedID, idType);
        });
        if (invalidRelationships.length > 0) {
            return `This relationship field has the following invalid relationships: ${invalidRelationships.map((err, invalid)=>{
                return `${err} ${JSON.stringify(invalid)}`;
            }).join(', ')}`;
        }
    }
    if (event === 'onChange') {
        return true;
    }
    return validateFilterOptions(value, options);
};
const select = (value, { data, filterOptions, hasMany, options, req, req: { t }, required, siblingData })=>{
    const filteredOptions = typeof filterOptions === 'function' ? filterOptions({
        data,
        options,
        req,
        siblingData
    }) : options;
    if (Array.isArray(value) && value.some((input)=>!filteredOptions.some((option)=>option === input || typeof option !== 'string' && option?.value === input))) {
        return t('validation:invalidSelection');
    }
    // Check for duplicate values when hasMany is true
    if (hasMany && Array.isArray(value) && value.length > 1) {
        const counts = new Map();
        for (const item of value){
            counts.set(item, (counts.get(item) || 0) + 1);
        }
        const duplicates = [];
        for (const [item, count] of counts.entries()){
            if (count > 1) {
                // Add the item 'count' times to show all occurrences
                for(let i = 0; i < count; i++){
                    duplicates.push(item);
                }
            }
        }
        if (duplicates.length > 0) {
            return duplicates.reduce((err, duplicate, i)=>{
                return `${err} ${JSON.stringify(duplicate)}${i < duplicates.length - 1 ? ',' : ''}`;
            }, t('validation:invalidSelections'));
        }
    }
    if (typeof value === 'string' && !filteredOptions.some((option)=>option === value || typeof option !== 'string' && option.value === value)) {
        return t('validation:invalidSelection');
    }
    if (required && (typeof value === 'undefined' || value === null || hasMany && Array.isArray(value) && value?.length === 0)) {
        return t('validation:required');
    }
    return true;
};
const radio = (value, { options, req: { t }, required })=>{
    if (value) {
        const valueMatchesOption = options.some((option)=>option === value || typeof option !== 'string' && option.value === value);
        return valueMatchesOption || t('validation:invalidSelection');
    }
    return required ? t('validation:required') : true;
};
const point = (value = [
    '',
    ''
], { req: { t }, required })=>{
    if (value === null) {
        if (required) {
            return t('validation:required');
        }
        return true;
    }
    const lng = parseFloat(String(value[0]));
    const lat = parseFloat(String(value[1]));
    if (required && (value[0] && value[1] && typeof lng !== 'number' && typeof lat !== 'number' || Number.isNaN(lng) || Number.isNaN(lat) || Array.isArray(value) && value.length !== 2)) {
        return t('validation:requiresTwoNumbers');
    }
    if (value[1] && Number.isNaN(lng) || value[0] && Number.isNaN(lat)) {
        return t('validation:invalidInput');
    }
    // Validate longitude bounds (-180 to 180)
    if (value[0] && !Number.isNaN(lng) && (lng < -180 || lng > 180)) {
        return t('validation:longitudeOutOfBounds');
    }
    // Validate latitude bounds (-90 to 90)
    if (value[1] && !Number.isNaN(lat) && (lat < -90 || lat > 90)) {
        return t('validation:latitudeOutOfBounds');
    }
    return true;
};
const validations = {
    array,
    blocks,
    checkbox,
    code,
    confirmPassword,
    date,
    email,
    json,
    number,
    password,
    point,
    radio,
    relationship,
    richText,
    select,
    text,
    textarea,
    upload
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/folders/utils/formatFolderOrDocumentItem.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatFolderOrDocumentItem",
    ()=>formatFolderOrDocumentItem
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$uploads$2f$isImage$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/uploads/isImage.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$getBestFitFromSizes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getBestFitFromSizes.js [app-client] (ecmascript)");
;
;
function formatFolderOrDocumentItem({ folderFieldName, isUpload, relationTo, useAsTitle, value }) {
    const itemValue = {
        id: value?.id,
        _folderOrDocumentTitle: String(useAsTitle && value?.[useAsTitle] || value['id']),
        createdAt: value?.createdAt,
        folderID: value?.[folderFieldName],
        folderType: value?.folderType || [],
        updatedAt: value?.updatedAt
    };
    if (isUpload) {
        itemValue.filename = value.filename;
        itemValue.mimeType = value.mimeType;
        itemValue.url = value.thumbnailURL || ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$uploads$2f$isImage$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isImage"])(value.mimeType) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$getBestFitFromSizes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getBestFitFromSizes"])({
            sizes: value.sizes,
            targetSizeMax: 520,
            targetSizeMin: 300,
            url: value.url,
            width: value.width
        }) : undefined);
    }
    return {
        itemKey: `${relationTo}-${value.id}`,
        relationTo,
        value: itemValue
    };
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/preferences/keys.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Centralized preference keys used throughout Payload admin UI.
 * Import these constants instead of using string literals to prevent typos.
 */ __turbopack_context__.s([
    "PREFERENCE_KEYS",
    ()=>PREFERENCE_KEYS
]);
const PREFERENCE_KEYS = {
    /**
   * Stores browse by folder view state
   */ BROWSE_BY_FOLDER: 'browse-by-folder',
    /**
   * Stores dashboard layout configuration
   */ DASHBOARD_LAYOUT: 'dashboard-layout',
    /**
   * Stores navigation group collapse/expand state and nav open/closed state
   */ NAV: 'nav'
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/types/constants.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SAFE_FIELD_PATH_REGEX",
    ()=>SAFE_FIELD_PATH_REGEX,
    "validOperatorSet",
    ()=>validOperatorSet,
    "validOperators",
    ()=>validOperators
]);
const validOperators = [
    'equals',
    'contains',
    'not_equals',
    'in',
    'all',
    'not_in',
    'exists',
    'greater_than',
    'greater_than_equal',
    'less_than',
    'less_than_equal',
    'like',
    'not_like',
    'within',
    'intersects',
    'near'
];
const validOperatorSet = new Set(validOperators);
const SAFE_FIELD_PATH_REGEX = /^\w+(?:\.\w+)*$/;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/uploads/formatFilesize.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatFilesize",
    ()=>formatFilesize
]);
function formatFilesize(bytes, decimals = 0) {
    if (bytes === 0) {
        return '0 bytes';
    }
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = [
        ' bytes',
        'KB',
        'MB',
        'GB',
        'TB',
        'PB',
        'EB',
        'ZB',
        'YB'
    ];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / k ** i).toFixed(dm))}${sizes[i]}`;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/uploads/isImage.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isImage",
    ()=>isImage
]);
function isImage(mimeType) {
    return [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/svg+xml',
        'image/webp',
        'image/avif',
        'image/jxl'
    ].indexOf(mimeType) > -1;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/appendUploadSelectFields.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Mutates the incoming select object to append fields required for upload thumbnails
 * @param collectionConfig
 * @param select
 */ __turbopack_context__.s([
    "appendUploadSelectFields",
    ()=>appendUploadSelectFields
]);
const appendUploadSelectFields = ({ collectionConfig, select })=>{
    if (!collectionConfig.upload || !select) {
        return;
    }
    select.mimeType = true;
    select.thumbnailURL = true;
    if (collectionConfig.upload.imageSizes && collectionConfig.upload.imageSizes.length > 0) {
        if (collectionConfig.upload.adminThumbnail && typeof collectionConfig.upload.adminThumbnail === 'string') {
            /** Only return image size properties that are required to generate the adminThumbnailURL */ select.sizes = {
                [collectionConfig.upload.adminThumbnail]: {
                    filename: true
                }
            };
        } else {
            /** Only return image size properties that are required for thumbnails */ select.sizes = collectionConfig.upload.imageSizes.reduce((acc, imageSizeConfig)=>{
                return {
                    ...acc,
                    [imageSizeConfig.name]: {
                        filename: true,
                        url: true,
                        width: true
                    }
                };
            }, {});
        }
    } else {
        select.url = true;
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/combineWhereConstraints.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "combineWhereConstraints",
    ()=>combineWhereConstraints
]);
function combineWhereConstraints(constraints, as = 'and') {
    if (constraints.length === 0) {
        return {};
    }
    const reducedConstraints = constraints.reduce((acc, constraint)=>{
        if (constraint && typeof constraint === 'object' && Object.keys(constraint).length > 0) {
            if (as in constraint) {
                // merge the objects under the shared key
                acc[as] = [
                    ...acc[as],
                    ...constraint[as]
                ];
            } else {
                // the constraint does not share the key
                acc[as]?.push(constraint);
            }
        }
        return acc;
    }, {
        [as]: []
    });
    if (reducedConstraints[as]?.length === 0) {
        // If there are no constraints, return an empty object
        return {};
    }
    return reducedConstraints;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/deepCopyObject.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "deepCopyObject",
    ()=>deepCopyObject,
    "deepCopyObjectComplex",
    ()=>deepCopyObjectComplex,
    "deepCopyObjectSimple",
    ()=>deepCopyObjectSimple,
    "deepCopyObjectSimpleWithoutReactComponents",
    ()=>deepCopyObjectSimpleWithoutReactComponents
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$buffer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/buffer/index.js [app-client] (ecmascript)");
/* eslint-disable @typescript-eslint/no-explicit-any */ /*
Main deepCopyObject handling - from rfdc: https://github.com/davidmarkclements/rfdc/blob/master/index.js

Copyright 2019 "David Mark Clements <david.mark.clements@gmail.com>"

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions
of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
*/ function copyBuffer(cur) {
    if (cur instanceof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$buffer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Buffer"]) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$buffer$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Buffer"].from(cur);
    }
    return new cur.constructor(cur.buffer.slice(), cur.byteOffset, cur.length);
}
const constructorHandlers = new Map();
constructorHandlers.set(Date, (o)=>new Date(o));
constructorHandlers.set(Map, (o, fn)=>new Map(cloneArray(Array.from(o), fn)));
constructorHandlers.set(Set, (o, fn)=>new Set(cloneArray(Array.from(o), fn)));
constructorHandlers.set(RegExp, (regex)=>new RegExp(regex.source, regex.flags));
let handler = null;
function cloneArray(a, fn) {
    const keys = Object.keys(a);
    const a2 = new Array(keys.length);
    for(let i = 0; i < keys.length; i++){
        const k = keys[i];
        const cur = a[k];
        if (typeof cur !== 'object' || cur === null) {
            a2[k] = cur;
        } else if (cur instanceof RegExp) {
            a2[k] = new RegExp(cur.source, cur.flags);
        } else if (cur.constructor !== Object && (handler = constructorHandlers.get(cur.constructor))) {
            a2[k] = handler(cur, fn);
        } else if (ArrayBuffer.isView(cur)) {
            a2[k] = copyBuffer(cur);
        } else {
            a2[k] = fn(cur);
        }
    }
    return a2;
}
const deepCopyObject = (o)=>{
    if (typeof o !== 'object' || o === null) {
        return o;
    }
    if (Array.isArray(o)) {
        return cloneArray(o, deepCopyObject);
    }
    if (o instanceof RegExp) {
        return new RegExp(o.source, o.flags);
    }
    if (o.constructor !== Object && (handler = constructorHandlers.get(o.constructor))) {
        return handler(o, deepCopyObject);
    }
    const o2 = {};
    for(const k in o){
        if (Object.hasOwnProperty.call(o, k) === false) {
            continue;
        }
        const cur = o[k];
        if (typeof cur !== 'object' || cur === null) {
            o2[k] = cur;
        } else if (cur instanceof RegExp) {
            o2[k] = new RegExp(cur.source, cur.flags);
        } else if (cur.constructor !== Object && (handler = constructorHandlers.get(cur.constructor))) {
            o2[k] = handler(cur, deepCopyObject);
        } else if (ArrayBuffer.isView(cur)) {
            o2[k] = copyBuffer(cur);
        } else {
            o2[k] = deepCopyObject(cur);
        }
    }
    return o2;
};
function deepCopyObjectSimple(value, filterUndefined = false) {
    if (typeof value !== 'object' || value === null) {
        return value;
    } else if (Array.isArray(value)) {
        return value.map((e)=>typeof e !== 'object' || e === null ? e : deepCopyObjectSimple(e, filterUndefined));
    } else {
        if (value instanceof Date) {
            return new Date(value);
        }
        const ret = {};
        for(const k in value){
            const v = value[k];
            if (filterUndefined && v === undefined) {
                continue;
            }
            ret[k] = typeof v !== 'object' || v === null ? v : deepCopyObjectSimple(v, filterUndefined);
        }
        return ret;
    }
}
function deepCopyObjectSimpleWithoutReactComponents(value, opts = {}) {
    if (typeof value === 'object' && value !== null && '$$typeof' in value && typeof value.$$typeof === 'symbol') {
        return undefined;
    } else if (typeof value !== 'object' || value === null) {
        return value;
    } else if (Array.isArray(value)) {
        return value.map((e)=>typeof e !== 'object' || e === null ? e : deepCopyObjectSimpleWithoutReactComponents(e, opts));
    } else {
        // Handle File objects by returning them as-is (don't serialize to plain object) or exclude if excludeFiles is provided
        if (value instanceof File) {
            if (opts.excludeFiles) {
                return undefined;
            }
            return value;
        }
        if (value instanceof Date) {
            return new Date(value);
        }
        const ret = {};
        for(const k in value){
            const v = value[k];
            ret[k] = typeof v !== 'object' || v === null ? v : deepCopyObjectSimpleWithoutReactComponents(v, opts);
        }
        return ret;
    }
}
function deepCopyObjectComplex(object, cache = new WeakMap()) {
    if (object === null) {
        return null;
    }
    if (cache.has(object)) {
        return cache.get(object);
    }
    // Handle File
    if (object instanceof File) {
        return object;
    }
    // Handle Date
    if (object instanceof Date) {
        return new Date(object.getTime());
    }
    // Handle RegExp
    if (object instanceof RegExp) {
        return new RegExp(object.source, object.flags);
    }
    // Handle Map
    if (object instanceof Map) {
        const clonedMap = new Map();
        cache.set(object, clonedMap);
        for (const [key, value] of object.entries()){
            clonedMap.set(key, deepCopyObjectComplex(value, cache));
        }
        return clonedMap;
    }
    // Handle Set
    if (object instanceof Set) {
        const clonedSet = new Set();
        cache.set(object, clonedSet);
        for (const value of object.values()){
            clonedSet.add(deepCopyObjectComplex(value, cache));
        }
        return clonedSet;
    }
    // Handle Array and Object
    if (typeof object === 'object' && object !== null) {
        if ('$$typeof' in object && typeof object.$$typeof === 'symbol') {
            return object;
        }
        const clonedObject = Array.isArray(object) ? [] : Object.create(Object.getPrototypeOf(object));
        cache.set(object, clonedObject);
        for(const key in object){
            if (Object.prototype.hasOwnProperty.call(object, key) || Object.getOwnPropertySymbols(object).includes(key)) {
                clonedObject[key] = deepCopyObjectComplex(object[key], cache);
            }
        }
        return clonedObject;
    }
    // Handle all other cases
    return object;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/escapeRegExp.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Escapes special characters in a string for use in a regular expression
 * @param string - The string to escape
 * @returns The escaped string safe for use in RegExp
 */ __turbopack_context__.s([
    "escapeRegExp",
    ()=>escapeRegExp
]);
const escapeRegExp = (string)=>string.replace(/[\\^$*+?.()|[\]{}]/g, '\\$&');
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/extractID.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "extractID",
    ()=>extractID
]);
const extractID = (objectOrID)=>{
    if (typeof objectOrID === 'string' || typeof objectOrID === 'number') {
        return objectOrID;
    }
    return objectOrID.id;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/flattenTopLevelFields.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "flattenTopLevelFields",
    ()=>flattenTopLevelFields
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/utilities/getTranslation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/config/types.js [app-client] (ecmascript)");
;
;
function flattenTopLevelFields(fields = [], options) {
    const normalizedOptions = typeof options === 'boolean' ? {
        keepPresentationalFields: options
    } : options ?? {};
    const { i18n, keepPresentationalFields, labelPrefix, moveSubFieldsToTop = false, pathPrefix } = normalizedOptions;
    return fields.reduce((acc, field)=>{
        // If a group field has subfields and has a name, otherwise we catch it below along with collapsible and row fields
        if (field.type === 'group' && 'fields' in field) {
            if (moveSubFieldsToTop) {
                const isNamedGroup = 'name' in field && typeof field.name === 'string' && !!field.name;
                const groupName = 'name' in field ? field.name : undefined;
                const translatedLabel = 'label' in field && field.label && i18n ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslation"])(field.label, i18n) : undefined;
                const labelWithPrefix = labelPrefix ? `${labelPrefix} > ${translatedLabel ?? groupName}` : translatedLabel ?? groupName;
                const nameWithPrefix = 'name' in field && field.name ? pathPrefix ? `${pathPrefix}.${field.name}` : field.name : pathPrefix;
                acc.push(// so that `buildColumnState` can detect and render a column if the group
                // has a custom admin Cell component defined in its configuration.
                // See: packages/ui/src/providers/TableColumns/buildColumnState/index.tsx
                field, ...flattenTopLevelFields(field.fields, {
                    i18n,
                    keepPresentationalFields,
                    labelPrefix: isNamedGroup ? labelWithPrefix : labelPrefix,
                    moveSubFieldsToTop,
                    pathPrefix: isNamedGroup ? nameWithPrefix : pathPrefix
                }));
            } else {
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field)) {
                    // Hoisting diabled - keep as top level field
                    acc.push(field);
                } else {
                    acc.push(...flattenTopLevelFields(field.fields, options));
                }
            }
        } else if (field.type === 'tabs' && 'tabs' in field) {
            return [
                ...acc,
                ...field.tabs.reduce((tabFields, tab)=>{
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["tabHasName"])(tab)) {
                        if (moveSubFieldsToTop) {
                            const translatedLabel = 'label' in tab && tab.label && i18n ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslation"])(tab.label, i18n) : undefined;
                            const labelWithPrefixForTab = labelPrefix ? `${labelPrefix} > ${translatedLabel ?? tab.name}` : translatedLabel ?? tab.name;
                            const pathPrefixForTab = tab.name ? pathPrefix ? `${pathPrefix}.${tab.name}` : tab.name : pathPrefix;
                            return [
                                ...tabFields,
                                ...flattenTopLevelFields(tab.fields, {
                                    i18n,
                                    keepPresentationalFields,
                                    labelPrefix: labelWithPrefixForTab,
                                    moveSubFieldsToTop,
                                    pathPrefix: pathPrefixForTab
                                })
                            ];
                        } else {
                            // Named tab, hoisting disabled: keep as top-level field
                            return [
                                ...tabFields,
                                {
                                    ...tab,
                                    type: 'tab'
                                }
                            ];
                        }
                    } else {
                        // Unnamed tab: always hoist its fields
                        return [
                            ...tabFields,
                            ...flattenTopLevelFields(tab.fields, options)
                        ];
                    }
                }, [])
            ];
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldHasSubFields"])(field) && [
            'collapsible',
            'row'
        ].includes(field.type)) {
            // Recurse into row and collapsible
            acc.push(...flattenTopLevelFields(field.fields, options));
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field) || keepPresentationalFields && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldIsPresentationalOnly"])(field)) {
            // Ignore nested `id` fields when inside nested structure
            if (field.name === 'id' && labelPrefix !== undefined) {
                return acc;
            }
            const translatedLabel = 'label' in field && field.label && i18n ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$translations$2f$dist$2f$utilities$2f$getTranslation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getTranslation"])(field.label, i18n) : undefined;
            const name = 'name' in field ? field.name : undefined;
            const isHoistingFromGroup = pathPrefix !== undefined || labelPrefix !== undefined;
            acc.push({
                ...field,
                ...moveSubFieldsToTop && isHoistingFromGroup && {
                    accessor: pathPrefix && name ? `${pathPrefix}.${name}` : name ?? '',
                    labelWithPrefix: labelPrefix ? `${labelPrefix} > ${translatedLabel ?? name}` : translatedLabel ?? name
                }
            });
        }
        return acc;
    }, []);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatAdminURL",
    ()=>formatAdminURL
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
const formatAdminURL = (args)=>{
    const { adminRoute, apiRoute, includeBasePath: includeBasePathArg, path = '', relative = false, serverURL } = args;
    const basePath = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].env.NEXT_BASE_PATH || args.basePath || '';
    const routePath = adminRoute || apiRoute;
    const segments = [
        routePath && routePath !== '/' && routePath,
        path && path
    ].filter(Boolean);
    const pathname = segments.join('') || '/';
    const pathnameWithBase = (basePath + pathname).replace(/\/$/, '') || '/';
    const includeBasePath = includeBasePathArg ?? (adminRoute ? false : true);
    if (relative || !serverURL) {
        if (includeBasePath && basePath) {
            return pathnameWithBase;
        }
        return pathname;
    }
    const serverURLObj = new URL(serverURL);
    return new URL(pathnameWithBase, serverURLObj.origin).toString();
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatLabels.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "formatLabels",
    ()=>formatLabels,
    "formatNames",
    ()=>formatNames,
    "toWords",
    ()=>toWords
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$pluralize$2f$pluralize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/pluralize/pluralize.js [app-client] (ecmascript)");
;
const { isPlural, singular } = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$pluralize$2f$pluralize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
const capitalizeFirstLetter = (string)=>string.charAt(0).toUpperCase() + string.slice(1);
const toWords = (inputString, joinWords = false)=>{
    const notNullString = inputString || '';
    const trimmedString = notNullString.trim();
    const arrayOfStrings = trimmedString.split(/[\s-]/);
    const splitStringsArray = [];
    arrayOfStrings.forEach((tempString)=>{
        if (tempString !== '') {
            const splitWords = tempString.split(/(?=[A-Z])/).join(' ');
            splitStringsArray.push(capitalizeFirstLetter(splitWords));
        }
    });
    return joinWords ? splitStringsArray.join('').replace(/\s/g, '') : splitStringsArray.join(' ');
};
const formatLabels = (slug)=>{
    const words = toWords(slug);
    return isPlural(slug) ? {
        plural: words,
        singular: singular(words)
    } : {
        plural: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$pluralize$2f$pluralize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(words),
        singular: words
    };
};
const formatNames = (slug)=>{
    const words = toWords(slug, true);
    return isPlural(slug) ? {
        plural: words,
        singular: singular(words)
    } : {
        plural: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$pluralize$2f$pluralize$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(words),
        singular: words
    };
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getBestFitFromSizes.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Takes image sizes and a target range and returns the url of the image within that range.
 * If no images fit within the range, it selects the next smallest adequate image, the original,
 * or the largest smaller image if no better fit exists.
 *
 * @param sizes The given FileSizes.
 * @param targetSizeMax The ideal image maximum width. Defaults to 180.
 * @param targetSizeMin The ideal image minimum width. Defaults to 40.
 * @param thumbnailURL The thumbnail url set in config. If passed a url, will return early with it.
 * @param url The url of the original file.
 * @param width The width of the original file.
 * @returns A url of the best fit file.
 */ __turbopack_context__.s([
    "getBestFitFromSizes",
    ()=>getBestFitFromSizes
]);
const getBestFitFromSizes = ({ sizes, targetSizeMax = 180, targetSizeMin = 40, thumbnailURL, url, width })=>{
    if (thumbnailURL) {
        return thumbnailURL;
    }
    if (!sizes) {
        return url;
    }
    const bestFit = Object.values(sizes).reduce((closest, current)=>{
        if (!current.width || current.width < targetSizeMin) {
            return closest;
        }
        if (current.width >= targetSizeMin && current.width <= targetSizeMax) {
            return !closest.width || current.width < closest.width || closest.width < targetSizeMin || closest.width > targetSizeMax ? current : closest;
        }
        if (!closest.width || !closest.original && closest.width < targetSizeMin && current.width > closest.width || closest.width > targetSizeMax && current.width < closest.width) {
            return current;
        }
        return closest;
    }, {
        original: true,
        url,
        width
    });
    return bestFit.url || url;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getDataByPath.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getDataByPath",
    ()=>getDataByPath
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/unflatten.js [app-client] (ecmascript)");
;
const getDataByPath = (fields, path)=>{
    const pathPrefixToRemove = path.substring(0, path.lastIndexOf('.') + 1);
    const name = path.split('.').pop();
    const data = {};
    Object.keys(fields).forEach((key)=>{
        if (!fields[key]?.disableFormData && (key.indexOf(`${path}.`) === 0 || key === path)) {
            data[key.replace(pathPrefixToRemove, '')] = fields[key]?.value;
            if (fields[key]?.rows && fields[key].rows.length === 0) {
                data[key.replace(pathPrefixToRemove, '')] = [];
            }
        }
    });
    const unflattenedData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["unflatten"])(data);
    return unflattenedData?.[name];
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getFieldPermissions.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/* eslint-disable @typescript-eslint/no-explicit-any */ /**
 * Gets read and operation-level permissions for a given field based on cascading field permissions.
 * @returns An object with the following properties:
 * - `operation`: Whether the user has permission to perform the operation on the field (`create` or `update`).
 * - `permissions`: The field-level permissions.
 * - `read`: Whether the user has permission to read the field.
 */ __turbopack_context__.s([
    "getFieldPermissions",
    ()=>getFieldPermissions
]);
const getFieldPermissions = ({ collectionPermissions, field, operation, parentName, permissions })=>{
    // First, calculate permissions using the existing logic
    const fieldOperation = permissions === true || permissions?.[operation] === true || permissions?.[parentName] === true || 'name' in field && typeof permissions === 'object' && permissions?.[field.name] && (permissions[field.name] === true || operation in permissions[field.name] && permissions[field.name][operation]);
    const fieldPermissions = permissions === undefined || permissions === null || permissions === true ? true : 'name' in field ? permissions[field.name] : permissions;
    const fieldRead = permissions === true || permissions?.read === true || permissions?.[parentName] === true || 'name' in field && typeof permissions === 'object' && permissions?.[field.name] && (permissions[field.name] === true || 'read' in permissions[field.name] && permissions[field.name].read);
    // Check if field permissions are effectively empty/missing
    const hasFieldPermissions = permissions === true || typeof permissions === 'object' && permissions !== null && Object.keys(permissions).length > 0;
    // If no field permissions are defined, fallback to collection permissions
    if (!hasFieldPermissions && collectionPermissions) {
        const collectionRead = Boolean(collectionPermissions.read);
        let collectionOperation = false;
        // Check operation-specific permission on collection
        if (operation === 'create' && 'create' in collectionPermissions) {
            collectionOperation = Boolean(collectionPermissions.create);
        } else if (operation === 'update') {
            collectionOperation = Boolean(collectionPermissions.update);
        }
        return {
            operation: collectionOperation,
            permissions: {
                read: collectionRead
            },
            read: collectionRead
        };
    }
    // Return the calculated permissions
    return {
        operation: Boolean(fieldOperation),
        permissions: fieldPermissions,
        read: Boolean(fieldRead)
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getObjectDotNotation.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 *
 * @deprecated use getObjectDotNotation from `'payload/shared'` instead of `'payload'`
 *
 * @example
 *
 * ```ts
 * import { getObjectDotNotation } from 'payload/shared'
 *
 * const obj = { a: { b: { c: 42 } } }
 * const value = getObjectDotNotation<number>(obj, 'a.b.c', 0) // value is 42
 * const defaultValue = getObjectDotNotation<number>(obj, 'a.b.x', 0) // defaultValue is 0
 * ```
 */ __turbopack_context__.s([
    "getObjectDotNotation",
    ()=>getObjectDotNotation
]);
const getObjectDotNotation = (obj, path, defaultValue)=>{
    if (!path || !obj) {
        return defaultValue;
    }
    const result = path.split('.').reduce((o, i)=>o?.[i], obj);
    return result === undefined ? defaultValue : result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getSiblingData.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getSiblingData",
    ()=>getSiblingData
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$reduceFieldsToValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/reduceFieldsToValues.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/unflatten.js [app-client] (ecmascript)");
;
;
const getSiblingData = (fields, path)=>{
    if (!fields) {
        return null;
    }
    if (path.indexOf('.') === -1) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$reduceFieldsToValues$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["reduceFieldsToValues"])(fields, true);
    }
    const siblingFields = {};
    // Determine if the last segment of the path is an array-based row
    const pathSegments = path.split('.');
    const lastSegment = pathSegments[pathSegments.length - 1];
    const lastSegmentIsRowIndex = !Number.isNaN(Number(lastSegment));
    let parentFieldPath;
    if (lastSegmentIsRowIndex) {
        // If the last segment is a row index,
        // the sibling data is that row's contents
        // so create a parent field path that will
        // retrieve all contents of that row index only
        parentFieldPath = `${path}.`;
    } else {
        // Otherwise, the last path segment is a field name
        // and it should be removed
        parentFieldPath = path.substring(0, path.lastIndexOf('.') + 1);
    }
    Object.keys(fields).forEach((fieldKey)=>{
        if (!fields[fieldKey]?.disableFormData && fieldKey.indexOf(parentFieldPath) === 0) {
            siblingFields[fieldKey.replace(parentFieldPath, '')] = fields[fieldKey]?.value;
        }
    });
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["unflatten"])(siblingFields);
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getUniqueListBy.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getUniqueListBy",
    ()=>getUniqueListBy
]);
function getUniqueListBy(arr, key) {
    return [
        ...new Map(arr.map((item)=>[
                item[key],
                item
            ])).values()
    ];
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getVersionsConfig.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getAutosaveInterval",
    ()=>getAutosaveInterval,
    "getVersionsMax",
    ()=>getVersionsMax,
    "hasAutosaveEnabled",
    ()=>hasAutosaveEnabled,
    "hasDraftValidationEnabled",
    ()=>hasDraftValidationEnabled,
    "hasDraftsEnabled",
    ()=>hasDraftsEnabled,
    "hasLocalizeStatusEnabled",
    ()=>hasLocalizeStatusEnabled,
    "hasScheduledPublishEnabled",
    ()=>hasScheduledPublishEnabled
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$versions$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/versions/defaults.js [app-client] (ecmascript)");
;
const hasDraftsEnabled = (config)=>{
    return Boolean(config?.versions && typeof config.versions === 'object' && config.versions.drafts);
};
const hasLocalizeStatusEnabled = (config)=>{
    return Boolean(config?.versions && typeof config.versions === 'object' && config.versions.drafts && typeof config.versions.drafts === 'object' && config.versions.drafts.localizeStatus);
};
const hasAutosaveEnabled = (config)=>{
    return Boolean(config?.versions && typeof config.versions === 'object' && config.versions.drafts && typeof config.versions.drafts === 'object' && config.versions.drafts.autosave);
};
const hasDraftValidationEnabled = (config)=>{
    return Boolean(config?.versions && typeof config.versions === 'object' && config.versions.drafts && typeof config.versions.drafts === 'object' && config.versions.drafts.validate);
};
const hasScheduledPublishEnabled = (config)=>{
    return Boolean(config?.versions && typeof config.versions === 'object' && config.versions.drafts && typeof config.versions.drafts === 'object' && config.versions.drafts.schedulePublish);
};
const getVersionsMax = (config)=>{
    if (!config?.versions || typeof config.versions !== 'object') {
        return 0;
    }
    // Collections have maxPerDoc, globals have max
    if ('maxPerDoc' in config.versions) {
        return config.versions.maxPerDoc ?? 100;
    }
    if ('max' in config.versions) {
        return config.versions.max ?? 100;
    }
    return 0;
};
const getAutosaveInterval = (config)=>{
    let interval = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$versions$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["versionDefaults"].autosaveInterval;
    if (config?.versions && typeof config.versions === 'object' && config.versions.drafts && typeof config.versions.drafts === 'object' && config.versions.drafts.autosave && typeof config.versions.drafts.autosave === 'object') {
        interval = config.versions.drafts.autosave.interval ?? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$versions$2f$defaults$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["versionDefaults"].autosaveInterval;
    }
    return interval;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/isNumber.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isNumber",
    ()=>isNumber
]);
function isNumber(value) {
    if (value === null || value === undefined || typeof value === 'string' && value.trim() === '') {
        return false;
    }
    return !Number.isNaN(Number(value));
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/isReactComponent.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isReactClientComponent",
    ()=>isReactClientComponent,
    "isReactComponentOrFunction",
    ()=>isReactComponentOrFunction,
    "isReactServerComponentOrFunction",
    ()=>isReactServerComponentOrFunction
]);
const clientRefSymbol = Symbol.for('react.client.reference');
function isReactServerComponentOrFunction(component) {
    return typeof component === 'function' && component.$$typeof !== clientRefSymbol;
}
function isReactClientComponent(component) {
    return typeof component === 'function' && component.$$typeof === clientRefSymbol;
}
function isReactComponentOrFunction(component) {
    return typeof component === 'function';
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/isValidID.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "isValidID",
    ()=>isValidID
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-client] (ecmascript)");
;
const ObjectId = 'default' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"] ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].default : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
const isValidID = (value, type)=>{
    if (type === 'text' && value) {
        if ([
            'object',
            'string'
        ].includes(typeof value)) {
            const isObjectID = ObjectId.isValid(value);
            return typeof value === 'string' || isObjectID;
        }
        return false;
    }
    if (type === 'number' && typeof value === 'number' && !Number.isNaN(value)) {
        return true;
    }
    if (type === 'ObjectID') {
        return ObjectId.isValid(String(value));
    }
    return false;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/mergeListSearchAndWhere.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hoistQueryParamsToAnd",
    ()=>hoistQueryParamsToAnd,
    "mergeListSearchAndWhere",
    ()=>mergeListSearchAndWhere
]);
const isEmptyObject = (obj)=>Object.keys(obj).length === 0;
const hoistQueryParamsToAnd = (currentWhere, incomingWhere)=>{
    if (isEmptyObject(incomingWhere)) {
        return currentWhere;
    }
    if (isEmptyObject(currentWhere)) {
        return incomingWhere;
    }
    if ('and' in currentWhere && currentWhere.and) {
        currentWhere.and.push(incomingWhere);
    } else if ('or' in currentWhere) {
        currentWhere = {
            and: [
                currentWhere,
                incomingWhere
            ]
        };
    } else {
        currentWhere = {
            and: [
                currentWhere,
                incomingWhere
            ]
        };
    }
    return currentWhere;
};
const mergeListSearchAndWhere = ({ collectionConfig, search, where = {} })=>{
    if (search) {
        let copyOfWhere = {
            ...where || {}
        };
        const searchAsConditions = (collectionConfig.admin.listSearchableFields || [
            collectionConfig.admin?.useAsTitle || 'id'
        ]).map((fieldName)=>({
                [fieldName]: {
                    like: search
                }
            }));
        if (searchAsConditions.length > 0) {
            copyOfWhere = hoistQueryParamsToAnd(copyOfWhere, {
                or: searchAsConditions
            });
        }
        if (!isEmptyObject(copyOfWhere)) {
            where = copyOfWhere;
        }
    }
    return where;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/reduceFieldsToValues.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "reduceFieldsToValues",
    ()=>reduceFieldsToValues
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/unflatten.js [app-client] (ecmascript)");
;
const reduceFieldsToValues = (fields, unflatten, ignoreDisableFormData)=>{
    let data = {};
    if (!fields) {
        return data;
    }
    Object.keys(fields).forEach((key)=>{
        if (ignoreDisableFormData === true || !fields[key]?.disableFormData) {
            data[key] = fields[key]?.value;
        }
    });
    if (unflatten) {
        data = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$unflatten$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["unflatten"])(data);
    }
    return data;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/setsAreEqual.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "setsAreEqual",
    ()=>setsAreEqual
]);
const setsAreEqual = (xs, ys)=>xs.size === ys.size && [
        ...xs
    ].every((x)=>ys.has(x));
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/toKebabCase.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "toKebabCase",
    ()=>toKebabCase
]);
const toKebabCase = (string)=>string?.replace(/([a-z])([A-Z])/g, '$1-$2').replace(/\s+/g, '-').toLowerCase();
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/transformColumnPreferences.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Transforms various forms of columns into `ColumnPreference[]` which is what is stored in the user's preferences table
 * In React state, for example, columns are stored in in their entirety, including React components: `[{ accessor: 'title', active: true, Label: React.ReactNode, ... }]`
 * In the URL, they are stored as an array of strings: `['title', '-slug']`, where the `-` prefix is used to indicate that the column is inactive
 * However in the database, columns must be in this exact shape: `[{ accessor: 'title', active: true }, { accessor: 'slug', active: false }]`
 * This means that when handling columns, they need to be consistently transformed back and forth
 */ __turbopack_context__.s([
    "transformColumnsToPreferences",
    ()=>transformColumnsToPreferences,
    "transformColumnsToSearchParams",
    ()=>transformColumnsToSearchParams
]);
const transformColumnsToPreferences = (columns)=>{
    if (!columns) {
        return undefined;
    }
    let columnsToTransform = columns;
    // Columns that originate from the URL are a stringified JSON array and need to be parsed first
    if (typeof columns === 'string') {
        try {
            columnsToTransform = JSON.parse(columns);
        } catch (e) {
            console.error('Error parsing columns', columns, e); // eslint-disable-line no-console
        }
    }
    if (columnsToTransform && Array.isArray(columnsToTransform)) {
        return columnsToTransform.map((col)=>{
            if (typeof col === 'string') {
                const active = col[0] !== '-';
                return {
                    accessor: active ? col : col.slice(1),
                    active
                };
            }
            return {
                accessor: col.accessor,
                active: col.active
            };
        });
    }
};
const transformColumnsToSearchParams = (columns)=>{
    return columns?.map((col)=>col.active ? col.accessor : `-${col.accessor}`);
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/transformWhereQuery.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Transforms a basic "where" query into a format in which the "where builder" can understand.
 * Even though basic queries are valid, we need to hoist them into the "and" / "or" format.
 * Use this function alongside `validateWhereQuery` to check that for valid queries before transforming.
 * @example
 * Inaccurate: [text][equals]=example%20post
 * Accurate: [or][0][and][0][text][equals]=example%20post
 */ __turbopack_context__.s([
    "transformWhereQuery",
    ()=>transformWhereQuery
]);
const transformWhereQuery = (whereQuery)=>{
    if (!whereQuery) {
        return {};
    }
    // Check if 'whereQuery' has 'or' field but no 'and'. This is the case for "correct" queries
    if (whereQuery.or && !whereQuery.and) {
        return {
            or: whereQuery.or.map((query)=>{
                // ...but if the or query does not have an and, we need to add it
                if (!query.and) {
                    return {
                        and: [
                            query
                        ]
                    };
                }
                return query;
            })
        };
    }
    // Check if 'whereQuery' has 'and' field but no 'or'.
    if (whereQuery.and && !whereQuery.or) {
        return {
            or: [
                {
                    and: whereQuery.and
                }
            ]
        };
    }
    // Check if 'whereQuery' has neither 'or' nor 'and'.
    if (!whereQuery.or && !whereQuery.and) {
        return {
            or: [
                {
                    and: [
                        whereQuery
                    ]
                }
            ]
        };
    }
    // If 'whereQuery' has 'or' and 'and', just return it as it is.
    return whereQuery;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/unflatten.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "unflatten",
    ()=>unflatten
]);
/* eslint-disable @typescript-eslint/no-explicit-any */ /*
 * Copyright (c) 2014, Hugh Kennedy
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
 * 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */ /*
 * Copyright (c) 2020, Feross Aboukhadijeh <https://feross.org>
 * Reference: https://www.npmjs.com/package/is-buffer
 * All rights reserved.
 */ function isBuffer(obj) {
    return obj != null && obj.constructor != null && typeof obj.constructor.isBuffer === 'function' && obj.constructor.isBuffer(obj);
}
const unflatten = (target, opts)=>{
    opts = opts || {};
    const delimiter = opts.delimiter || '.';
    const overwrite = opts.overwrite || false;
    const recursive = opts.recursive || false;
    const result = {};
    const isbuffer = isBuffer(target);
    if (isbuffer || Object.prototype.toString.call(target) !== '[object Object]') {
        return target;
    }
    // safely ensure that the key is an integer.
    const getkey = (key)=>{
        const parsedKey = Number(key);
        return isNaN(parsedKey) || key.indexOf('.') !== -1 || opts.object ? key : parsedKey;
    };
    const sortedKeys = Object.keys(target).sort((keyA, keyB)=>keyA.length - keyB.length);
    sortedKeys.forEach((key)=>{
        const split = key.split(delimiter);
        let key1 = getkey(split.shift());
        let key2 = getkey(split[0]);
        let recipient = result;
        while(key2 !== undefined){
            if (key1 === '__proto__') {
                return;
            }
            const type = Object.prototype.toString.call(recipient[key1]);
            const isobject = type === '[object Object]' || type === '[object Array]';
            // do not write over falsey, non-undefined values if overwrite is false
            if (!overwrite && !isobject && typeof recipient[key1] !== 'undefined') {
                return;
            }
            if (overwrite && !isobject || !overwrite && recipient[key1] == null) {
                recipient[key1] = typeof key2 === 'number' && !opts.object ? [] : {};
            }
            recipient = recipient[key1];
            if (split.length > 0) {
                key1 = getkey(split.shift());
                key2 = getkey(split[0]);
            }
        }
        // unflatten again for 'messy objects'
        recipient[key1] = recursive ? unflatten(target[key], opts) : target[key];
    });
    return result;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/validateMimeType.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "validateMimeType",
    ()=>validateMimeType
]);
const validateMimeType = (mimeType, allowedMimeTypes)=>{
    if (allowedMimeTypes.length === 0) {
        return true;
    }
    const cleanedMimeTypes = allowedMimeTypes.map((v)=>v.replace('*', ''));
    return cleanedMimeTypes.some((cleanedMimeType)=>mimeType.startsWith(cleanedMimeType));
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/validateWhereQuery.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "validateWhereQuery",
    ()=>validateWhereQuery
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$types$2f$constants$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/types/constants.js [app-client] (ecmascript)");
;
const validateWhereQuery = (whereQuery)=>{
    if (whereQuery?.or && (whereQuery?.or?.length === 0 || whereQuery?.or?.length > 0 && whereQuery?.or?.[0]?.and && whereQuery?.or?.[0]?.and?.length > 0)) {
        // At this point we know that the whereQuery has 'or' and 'and' fields,
        // now let's check the structure and content of these fields.
        const isValid = whereQuery.or.every((orQuery)=>{
            if (orQuery.and && Array.isArray(orQuery.and)) {
                return orQuery.and.every((andQuery)=>{
                    if (typeof andQuery !== 'object') {
                        return false;
                    }
                    const andKeys = Object.keys(andQuery);
                    // If there are no keys, it's not a valid WhereField.
                    if (andKeys.length === 0) {
                        return false;
                    }
                    for (const key of andKeys){
                        const operator = Object.keys(andQuery[key])[0];
                        // Check if the key is a valid Operator.
                        if (!operator || !__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$types$2f$constants$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["validOperatorSet"].has(operator)) {
                            return false;
                        }
                    }
                    return true;
                });
            }
            return false;
        });
        return isValid;
    }
    return false;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/wait.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "wait",
    ()=>wait
]);
async function wait(ms) {
    return new Promise((resolve)=>{
        setTimeout(resolve, ms);
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/wordBoundariesRegex.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "wordBoundariesRegex",
    ()=>wordBoundariesRegex
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$escapeRegExp$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/escapeRegExp.js [app-client] (ecmascript)");
;
const wordBoundariesRegex = (input)=>{
    const words = input.split(' ');
    // Regex word boundaries that work for cyrillic characters - https://stackoverflow.com/a/47062016/1717697
    const wordBoundaryBefore = '(?:(?:[^\\p{L}\\p{N}])|^)' // Converted to a non-matching group instead of positive lookbehind for Safari
    ;
    const wordBoundaryAfter = '(?=[^\\p{L}\\p{N}]|$)';
    const regex = words.reduce((pattern, word, i)=>{
        const escapedWord = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$escapeRegExp$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["escapeRegExp"])(word);
        return `${pattern}(?=.*${wordBoundaryBefore}.*${escapedWord}.*${wordBoundaryAfter})${i + 1 === words.length ? '.+' : ''}`;
    }, '');
    return new RegExp(regex, 'i');
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/versions/defaults.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "versionDefaults",
    ()=>versionDefaults
]);
const versionDefaults = {
    autosaveInterval: 2000
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/pluralize/pluralize.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

/* global define */ (function(root, pluralize) {
    /* istanbul ignore else */ if ("TURBOPACK compile-time truthy", 1) {
        // Node.
        module.exports = pluralize();
    } else //TURBOPACK unreachable
    ;
})(/*TURBOPACK member replacement*/ __turbopack_context__.e, function() {
    // Rule storage - pluralize and singularize need to be run sequentially,
    // while other rules can be optimized using an object for instant lookups.
    var pluralRules = [];
    var singularRules = [];
    var uncountables = {};
    var irregularPlurals = {};
    var irregularSingles = {};
    /**
   * Sanitize a pluralization rule to a usable regular expression.
   *
   * @param  {(RegExp|string)} rule
   * @return {RegExp}
   */ function sanitizeRule(rule) {
        if (typeof rule === 'string') {
            return new RegExp('^' + rule + '$', 'i');
        }
        return rule;
    }
    /**
   * Pass in a word token to produce a function that can replicate the case on
   * another word.
   *
   * @param  {string}   word
   * @param  {string}   token
   * @return {Function}
   */ function restoreCase(word, token) {
        // Tokens are an exact match.
        if (word === token) return token;
        // Lower cased words. E.g. "hello".
        if (word === word.toLowerCase()) return token.toLowerCase();
        // Upper cased words. E.g. "WHISKY".
        if (word === word.toUpperCase()) return token.toUpperCase();
        // Title cased words. E.g. "Title".
        if (word[0] === word[0].toUpperCase()) {
            return token.charAt(0).toUpperCase() + token.substr(1).toLowerCase();
        }
        // Lower cased words. E.g. "test".
        return token.toLowerCase();
    }
    /**
   * Interpolate a regexp string.
   *
   * @param  {string} str
   * @param  {Array}  args
   * @return {string}
   */ function interpolate(str, args) {
        return str.replace(/\$(\d{1,2})/g, function(match, index) {
            return args[index] || '';
        });
    }
    /**
   * Replace a word using a rule.
   *
   * @param  {string} word
   * @param  {Array}  rule
   * @return {string}
   */ function replace(word, rule) {
        return word.replace(rule[0], function(match, index) {
            var result = interpolate(rule[1], arguments);
            if (match === '') {
                return restoreCase(word[index - 1], result);
            }
            return restoreCase(match, result);
        });
    }
    /**
   * Sanitize a word by passing in the word and sanitization rules.
   *
   * @param  {string}   token
   * @param  {string}   word
   * @param  {Array}    rules
   * @return {string}
   */ function sanitizeWord(token, word, rules) {
        // Empty string or doesn't need fixing.
        if (!token.length || uncountables.hasOwnProperty(token)) {
            return word;
        }
        var len = rules.length;
        // Iterate over the sanitization rules and use the first one to match.
        while(len--){
            var rule = rules[len];
            if (rule[0].test(word)) return replace(word, rule);
        }
        return word;
    }
    /**
   * Replace a word with the updated word.
   *
   * @param  {Object}   replaceMap
   * @param  {Object}   keepMap
   * @param  {Array}    rules
   * @return {Function}
   */ function replaceWord(replaceMap, keepMap, rules) {
        return function(word) {
            // Get the correct token and case restoration functions.
            var token = word.toLowerCase();
            // Check against the keep object map.
            if (keepMap.hasOwnProperty(token)) {
                return restoreCase(word, token);
            }
            // Check against the replacement map for a direct word replacement.
            if (replaceMap.hasOwnProperty(token)) {
                return restoreCase(word, replaceMap[token]);
            }
            // Run all the rules against the word.
            return sanitizeWord(token, word, rules);
        };
    }
    /**
   * Check if a word is part of the map.
   */ function checkWord(replaceMap, keepMap, rules, bool) {
        return function(word) {
            var token = word.toLowerCase();
            if (keepMap.hasOwnProperty(token)) return true;
            if (replaceMap.hasOwnProperty(token)) return false;
            return sanitizeWord(token, token, rules) === token;
        };
    }
    /**
   * Pluralize or singularize a word based on the passed in count.
   *
   * @param  {string}  word      The word to pluralize
   * @param  {number}  count     How many of the word exist
   * @param  {boolean} inclusive Whether to prefix with the number (e.g. 3 ducks)
   * @return {string}
   */ function pluralize(word, count, inclusive) {
        var pluralized = count === 1 ? pluralize.singular(word) : pluralize.plural(word);
        return (inclusive ? count + ' ' : '') + pluralized;
    }
    /**
   * Pluralize a word.
   *
   * @type {Function}
   */ pluralize.plural = replaceWord(irregularSingles, irregularPlurals, pluralRules);
    /**
   * Check if a word is plural.
   *
   * @type {Function}
   */ pluralize.isPlural = checkWord(irregularSingles, irregularPlurals, pluralRules);
    /**
   * Singularize a word.
   *
   * @type {Function}
   */ pluralize.singular = replaceWord(irregularPlurals, irregularSingles, singularRules);
    /**
   * Check if a word is singular.
   *
   * @type {Function}
   */ pluralize.isSingular = checkWord(irregularPlurals, irregularSingles, singularRules);
    /**
   * Add a pluralization rule to the collection.
   *
   * @param {(string|RegExp)} rule
   * @param {string}          replacement
   */ pluralize.addPluralRule = function(rule, replacement) {
        pluralRules.push([
            sanitizeRule(rule),
            replacement
        ]);
    };
    /**
   * Add a singularization rule to the collection.
   *
   * @param {(string|RegExp)} rule
   * @param {string}          replacement
   */ pluralize.addSingularRule = function(rule, replacement) {
        singularRules.push([
            sanitizeRule(rule),
            replacement
        ]);
    };
    /**
   * Add an uncountable word rule.
   *
   * @param {(string|RegExp)} word
   */ pluralize.addUncountableRule = function(word) {
        if (typeof word === 'string') {
            uncountables[word.toLowerCase()] = true;
            return;
        }
        // Set singular and plural references for the word.
        pluralize.addPluralRule(word, '$0');
        pluralize.addSingularRule(word, '$0');
    };
    /**
   * Add an irregular word definition.
   *
   * @param {string} single
   * @param {string} plural
   */ pluralize.addIrregularRule = function(single, plural) {
        plural = plural.toLowerCase();
        single = single.toLowerCase();
        irregularSingles[single] = plural;
        irregularPlurals[plural] = single;
    };
    /**
   * Irregular rules.
   */ [
        // Pronouns.
        [
            'I',
            'we'
        ],
        [
            'me',
            'us'
        ],
        [
            'he',
            'they'
        ],
        [
            'she',
            'they'
        ],
        [
            'them',
            'them'
        ],
        [
            'myself',
            'ourselves'
        ],
        [
            'yourself',
            'yourselves'
        ],
        [
            'itself',
            'themselves'
        ],
        [
            'herself',
            'themselves'
        ],
        [
            'himself',
            'themselves'
        ],
        [
            'themself',
            'themselves'
        ],
        [
            'is',
            'are'
        ],
        [
            'was',
            'were'
        ],
        [
            'has',
            'have'
        ],
        [
            'this',
            'these'
        ],
        [
            'that',
            'those'
        ],
        // Words ending in with a consonant and `o`.
        [
            'echo',
            'echoes'
        ],
        [
            'dingo',
            'dingoes'
        ],
        [
            'volcano',
            'volcanoes'
        ],
        [
            'tornado',
            'tornadoes'
        ],
        [
            'torpedo',
            'torpedoes'
        ],
        // Ends with `us`.
        [
            'genus',
            'genera'
        ],
        [
            'viscus',
            'viscera'
        ],
        // Ends with `ma`.
        [
            'stigma',
            'stigmata'
        ],
        [
            'stoma',
            'stomata'
        ],
        [
            'dogma',
            'dogmata'
        ],
        [
            'lemma',
            'lemmata'
        ],
        [
            'schema',
            'schemata'
        ],
        [
            'anathema',
            'anathemata'
        ],
        // Other irregular rules.
        [
            'ox',
            'oxen'
        ],
        [
            'axe',
            'axes'
        ],
        [
            'die',
            'dice'
        ],
        [
            'yes',
            'yeses'
        ],
        [
            'foot',
            'feet'
        ],
        [
            'eave',
            'eaves'
        ],
        [
            'goose',
            'geese'
        ],
        [
            'tooth',
            'teeth'
        ],
        [
            'quiz',
            'quizzes'
        ],
        [
            'human',
            'humans'
        ],
        [
            'proof',
            'proofs'
        ],
        [
            'carve',
            'carves'
        ],
        [
            'valve',
            'valves'
        ],
        [
            'looey',
            'looies'
        ],
        [
            'thief',
            'thieves'
        ],
        [
            'groove',
            'grooves'
        ],
        [
            'pickaxe',
            'pickaxes'
        ],
        [
            'passerby',
            'passersby'
        ]
    ].forEach(function(rule) {
        return pluralize.addIrregularRule(rule[0], rule[1]);
    });
    /**
   * Pluralization rules.
   */ [
        [
            /s?$/i,
            's'
        ],
        [
            /[^\u0000-\u007F]$/i,
            '$0'
        ],
        [
            /([^aeiou]ese)$/i,
            '$1'
        ],
        [
            /(ax|test)is$/i,
            '$1es'
        ],
        [
            /(alias|[^aou]us|t[lm]as|gas|ris)$/i,
            '$1es'
        ],
        [
            /(e[mn]u)s?$/i,
            '$1s'
        ],
        [
            /([^l]ias|[aeiou]las|[ejzr]as|[iu]am)$/i,
            '$1'
        ],
        [
            /(alumn|syllab|vir|radi|nucle|fung|cact|stimul|termin|bacill|foc|uter|loc|strat)(?:us|i)$/i,
            '$1i'
        ],
        [
            /(alumn|alg|vertebr)(?:a|ae)$/i,
            '$1ae'
        ],
        [
            /(seraph|cherub)(?:im)?$/i,
            '$1im'
        ],
        [
            /(her|at|gr)o$/i,
            '$1oes'
        ],
        [
            /(agend|addend|millenni|dat|extrem|bacteri|desiderat|strat|candelabr|errat|ov|symposi|curricul|automat|quor)(?:a|um)$/i,
            '$1a'
        ],
        [
            /(apheli|hyperbat|periheli|asyndet|noumen|phenomen|criteri|organ|prolegomen|hedr|automat)(?:a|on)$/i,
            '$1a'
        ],
        [
            /sis$/i,
            'ses'
        ],
        [
            /(?:(kni|wi|li)fe|(ar|l|ea|eo|oa|hoo)f)$/i,
            '$1$2ves'
        ],
        [
            /([^aeiouy]|qu)y$/i,
            '$1ies'
        ],
        [
            /([^ch][ieo][ln])ey$/i,
            '$1ies'
        ],
        [
            /(x|ch|ss|sh|zz)$/i,
            '$1es'
        ],
        [
            /(matr|cod|mur|sil|vert|ind|append)(?:ix|ex)$/i,
            '$1ices'
        ],
        [
            /\b((?:tit)?m|l)(?:ice|ouse)$/i,
            '$1ice'
        ],
        [
            /(pe)(?:rson|ople)$/i,
            '$1ople'
        ],
        [
            /(child)(?:ren)?$/i,
            '$1ren'
        ],
        [
            /eaux$/i,
            '$0'
        ],
        [
            /m[ae]n$/i,
            'men'
        ],
        [
            'thou',
            'you'
        ]
    ].forEach(function(rule) {
        return pluralize.addPluralRule(rule[0], rule[1]);
    });
    /**
   * Singularization rules.
   */ [
        [
            /s$/i,
            ''
        ],
        [
            /(ss)$/i,
            '$1'
        ],
        [
            /(wi|kni|(?:after|half|high|low|mid|non|night|[^\w]|^)li)ves$/i,
            '$1fe'
        ],
        [
            /(ar|(?:wo|[ae])l|[eo][ao])ves$/i,
            '$1f'
        ],
        [
            /ies$/i,
            'y'
        ],
        [
            /\b([pl]|zomb|(?:neck|cross)?t|coll|faer|food|gen|goon|group|lass|talk|goal|cut)ies$/i,
            '$1ie'
        ],
        [
            /\b(mon|smil)ies$/i,
            '$1ey'
        ],
        [
            /\b((?:tit)?m|l)ice$/i,
            '$1ouse'
        ],
        [
            /(seraph|cherub)im$/i,
            '$1'
        ],
        [
            /(x|ch|ss|sh|zz|tto|go|cho|alias|[^aou]us|t[lm]as|gas|(?:her|at|gr)o|[aeiou]ris)(?:es)?$/i,
            '$1'
        ],
        [
            /(analy|diagno|parenthe|progno|synop|the|empha|cri|ne)(?:sis|ses)$/i,
            '$1sis'
        ],
        [
            /(movie|twelve|abuse|e[mn]u)s$/i,
            '$1'
        ],
        [
            /(test)(?:is|es)$/i,
            '$1is'
        ],
        [
            /(alumn|syllab|vir|radi|nucle|fung|cact|stimul|termin|bacill|foc|uter|loc|strat)(?:us|i)$/i,
            '$1us'
        ],
        [
            /(agend|addend|millenni|dat|extrem|bacteri|desiderat|strat|candelabr|errat|ov|symposi|curricul|quor)a$/i,
            '$1um'
        ],
        [
            /(apheli|hyperbat|periheli|asyndet|noumen|phenomen|criteri|organ|prolegomen|hedr|automat)a$/i,
            '$1on'
        ],
        [
            /(alumn|alg|vertebr)ae$/i,
            '$1a'
        ],
        [
            /(cod|mur|sil|vert|ind)ices$/i,
            '$1ex'
        ],
        [
            /(matr|append)ices$/i,
            '$1ix'
        ],
        [
            /(pe)(rson|ople)$/i,
            '$1rson'
        ],
        [
            /(child)ren$/i,
            '$1'
        ],
        [
            /(eau)x?$/i,
            '$1'
        ],
        [
            /men$/i,
            'man'
        ]
    ].forEach(function(rule) {
        return pluralize.addSingularRule(rule[0], rule[1]);
    });
    /**
   * Uncountable rules.
   */ [
        // Singular words with no plurals.
        'adulthood',
        'advice',
        'agenda',
        'aid',
        'aircraft',
        'alcohol',
        'ammo',
        'analytics',
        'anime',
        'athletics',
        'audio',
        'bison',
        'blood',
        'bream',
        'buffalo',
        'butter',
        'carp',
        'cash',
        'chassis',
        'chess',
        'clothing',
        'cod',
        'commerce',
        'cooperation',
        'corps',
        'debris',
        'diabetes',
        'digestion',
        'elk',
        'energy',
        'equipment',
        'excretion',
        'expertise',
        'firmware',
        'flounder',
        'fun',
        'gallows',
        'garbage',
        'graffiti',
        'hardware',
        'headquarters',
        'health',
        'herpes',
        'highjinks',
        'homework',
        'housework',
        'information',
        'jeans',
        'justice',
        'kudos',
        'labour',
        'literature',
        'machinery',
        'mackerel',
        'mail',
        'media',
        'mews',
        'moose',
        'music',
        'mud',
        'manga',
        'news',
        'only',
        'personnel',
        'pike',
        'plankton',
        'pliers',
        'police',
        'pollution',
        'premises',
        'rain',
        'research',
        'rice',
        'salmon',
        'scissors',
        'series',
        'sewage',
        'shambles',
        'shrimp',
        'software',
        'species',
        'staff',
        'swine',
        'tennis',
        'traffic',
        'transportation',
        'trout',
        'tuna',
        'wealth',
        'welfare',
        'whiting',
        'wildebeest',
        'wildlife',
        'you',
        /pok[eé]mon$/i,
        // Regexes.
        /[^aeiou]ese$/i,
        /deer$/i,
        /fish$/i,
        /measles$/i,
        /o[iu]s$/i,
        /pox$/i,
        /sheep$/i
    ].forEach(pluralize.addUncountableRule);
    return pluralize;
});
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/checkPropTypes.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * Copyright (c) 2013-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ 'use strict';
var printWarning = function() {};
if ("TURBOPACK compile-time truthy", 1) {
    var ReactPropTypesSecret = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/ReactPropTypesSecret.js [app-client] (ecmascript)");
    var loggedTypeFailures = {};
    var has = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/has.js [app-client] (ecmascript)");
    printWarning = function(text) {
        var message = 'Warning: ' + text;
        if (typeof console !== 'undefined') {
            console.error(message);
        }
        try {
            // --- Welcome to debugging React ---
            // This error was thrown as a convenience so that you can use this stack
            // to find the callsite that caused this warning to fire.
            throw new Error(message);
        } catch (x) {}
    };
}
/**
 * Assert that the values match with the type specs.
 * Error messages are memorized and will only be shown once.
 *
 * @param {object} typeSpecs Map of name to a ReactPropType
 * @param {object} values Runtime values that need to be type-checked
 * @param {string} location e.g. "prop", "context", "child context"
 * @param {string} componentName Name of the component for error messages.
 * @param {?Function} getStack Returns the component stack.
 * @private
 */ function checkPropTypes(typeSpecs, values, location, componentName, getStack) {
    if ("TURBOPACK compile-time truthy", 1) {
        for(var typeSpecName in typeSpecs){
            if (has(typeSpecs, typeSpecName)) {
                var error;
                // Prop type validation may throw. In case they do, we don't want to
                // fail the render phase where it didn't fail before. So we log it.
                // After these have been cleaned up, we'll let them throw.
                try {
                    // This is intentionally an invariant that gets caught. It's the same
                    // behavior as without this statement except with a better message.
                    if (typeof typeSpecs[typeSpecName] !== 'function') {
                        var err = Error((componentName || 'React class') + ': ' + location + ' type `' + typeSpecName + '` is invalid; ' + 'it must be a function, usually from the `prop-types` package, but received `' + typeof typeSpecs[typeSpecName] + '`.' + 'This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`.');
                        err.name = 'Invariant Violation';
                        throw err;
                    }
                    error = typeSpecs[typeSpecName](values, typeSpecName, componentName, location, null, ReactPropTypesSecret);
                } catch (ex) {
                    error = ex;
                }
                if (error && !(error instanceof Error)) {
                    printWarning((componentName || 'React class') + ': type specification of ' + location + ' `' + typeSpecName + '` is invalid; the type checker ' + 'function must return `null` or an `Error` but returned a ' + typeof error + '. ' + 'You may have forgotten to pass an argument to the type checker ' + 'creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and ' + 'shape all require an argument).');
                }
                if (error instanceof Error && !(error.message in loggedTypeFailures)) {
                    // Only monitor this failure once because there tends to be a lot of the
                    // same error.
                    loggedTypeFailures[error.message] = true;
                    var stack = getStack ? getStack() : '';
                    printWarning('Failed ' + location + ' type: ' + error.message + (stack != null ? stack : ''));
                }
            }
        }
    }
}
/**
 * Resets warning cache when testing.
 *
 * @private
 */ checkPropTypes.resetWarningCache = function() {
    if (("TURBOPACK compile-time value", "development") !== 'production') {
        loggedTypeFailures = {};
    }
};
module.exports = checkPropTypes;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/factoryWithTypeCheckers.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * Copyright (c) 2013-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ 'use strict';
var ReactIs = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/react-is/index.js [app-client] (ecmascript)");
var assign = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/object-assign.js [app-client] (ecmascript)");
var ReactPropTypesSecret = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/ReactPropTypesSecret.js [app-client] (ecmascript)");
var has = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/has.js [app-client] (ecmascript)");
var checkPropTypes = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/checkPropTypes.js [app-client] (ecmascript)");
var printWarning = function() {};
if ("TURBOPACK compile-time truthy", 1) {
    printWarning = function(text) {
        var message = 'Warning: ' + text;
        if (typeof console !== 'undefined') {
            console.error(message);
        }
        try {
            // --- Welcome to debugging React ---
            // This error was thrown as a convenience so that you can use this stack
            // to find the callsite that caused this warning to fire.
            throw new Error(message);
        } catch (x) {}
    };
}
function emptyFunctionThatReturnsNull() {
    return null;
}
module.exports = function(isValidElement, throwOnDirectAccess) {
    /* global Symbol */ var ITERATOR_SYMBOL = typeof Symbol === 'function' && Symbol.iterator;
    var FAUX_ITERATOR_SYMBOL = '@@iterator'; // Before Symbol spec.
    /**
   * Returns the iterator method function contained on the iterable object.
   *
   * Be sure to invoke the function with the iterable as context:
   *
   *     var iteratorFn = getIteratorFn(myIterable);
   *     if (iteratorFn) {
   *       var iterator = iteratorFn.call(myIterable);
   *       ...
   *     }
   *
   * @param {?object} maybeIterable
   * @return {?function}
   */ function getIteratorFn(maybeIterable) {
        var iteratorFn = maybeIterable && (ITERATOR_SYMBOL && maybeIterable[ITERATOR_SYMBOL] || maybeIterable[FAUX_ITERATOR_SYMBOL]);
        if (typeof iteratorFn === 'function') {
            return iteratorFn;
        }
    }
    /**
   * Collection of methods that allow declaration and validation of props that are
   * supplied to React components. Example usage:
   *
   *   var Props = require('ReactPropTypes');
   *   var MyArticle = React.createClass({
   *     propTypes: {
   *       // An optional string prop named "description".
   *       description: Props.string,
   *
   *       // A required enum prop named "category".
   *       category: Props.oneOf(['News','Photos']).isRequired,
   *
   *       // A prop named "dialog" that requires an instance of Dialog.
   *       dialog: Props.instanceOf(Dialog).isRequired
   *     },
   *     render: function() { ... }
   *   });
   *
   * A more formal specification of how these methods are used:
   *
   *   type := array|bool|func|object|number|string|oneOf([...])|instanceOf(...)
   *   decl := ReactPropTypes.{type}(.isRequired)?
   *
   * Each and every declaration produces a function with the same signature. This
   * allows the creation of custom validation functions. For example:
   *
   *  var MyLink = React.createClass({
   *    propTypes: {
   *      // An optional string or URI prop named "href".
   *      href: function(props, propName, componentName) {
   *        var propValue = props[propName];
   *        if (propValue != null && typeof propValue !== 'string' &&
   *            !(propValue instanceof URI)) {
   *          return new Error(
   *            'Expected a string or an URI for ' + propName + ' in ' +
   *            componentName
   *          );
   *        }
   *      }
   *    },
   *    render: function() {...}
   *  });
   *
   * @internal
   */ var ANONYMOUS = '<<anonymous>>';
    // Important!
    // Keep this list in sync with production version in `./factoryWithThrowingShims.js`.
    var ReactPropTypes = {
        array: createPrimitiveTypeChecker('array'),
        bigint: createPrimitiveTypeChecker('bigint'),
        bool: createPrimitiveTypeChecker('boolean'),
        func: createPrimitiveTypeChecker('function'),
        number: createPrimitiveTypeChecker('number'),
        object: createPrimitiveTypeChecker('object'),
        string: createPrimitiveTypeChecker('string'),
        symbol: createPrimitiveTypeChecker('symbol'),
        any: createAnyTypeChecker(),
        arrayOf: createArrayOfTypeChecker,
        element: createElementTypeChecker(),
        elementType: createElementTypeTypeChecker(),
        instanceOf: createInstanceTypeChecker,
        node: createNodeChecker(),
        objectOf: createObjectOfTypeChecker,
        oneOf: createEnumTypeChecker,
        oneOfType: createUnionTypeChecker,
        shape: createShapeTypeChecker,
        exact: createStrictShapeTypeChecker
    };
    /**
   * inlined Object.is polyfill to avoid requiring consumers ship their own
   * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/is
   */ /*eslint-disable no-self-compare*/ function is(x, y) {
        // SameValue algorithm
        if (x === y) {
            // Steps 1-5, 7-10
            // Steps 6.b-6.e: +0 != -0
            return x !== 0 || 1 / x === 1 / y;
        } else {
            // Step 6.a: NaN == NaN
            return x !== x && y !== y;
        }
    }
    /*eslint-enable no-self-compare*/ /**
   * We use an Error-like object for backward compatibility as people may call
   * PropTypes directly and inspect their output. However, we don't use real
   * Errors anymore. We don't inspect their stack anyway, and creating them
   * is prohibitively expensive if they are created too often, such as what
   * happens in oneOfType() for any type before the one that matched.
   */ function PropTypeError(message, data) {
        this.message = message;
        this.data = data && typeof data === 'object' ? data : {};
        this.stack = '';
    }
    // Make `instanceof Error` still work for returned errors.
    PropTypeError.prototype = Error.prototype;
    function createChainableTypeChecker(validate) {
        if (("TURBOPACK compile-time value", "development") !== 'production') {
            var manualPropTypeCallCache = {};
            var manualPropTypeWarningCount = 0;
        }
        function checkType(isRequired, props, propName, componentName, location, propFullName, secret) {
            componentName = componentName || ANONYMOUS;
            propFullName = propFullName || propName;
            if (secret !== ReactPropTypesSecret) {
                if (throwOnDirectAccess) {
                    // New behavior only for users of `prop-types` package
                    var err = new Error('Calling PropTypes validators directly is not supported by the `prop-types` package. ' + 'Use `PropTypes.checkPropTypes()` to call them. ' + 'Read more at http://fb.me/use-check-prop-types');
                    err.name = 'Invariant Violation';
                    throw err;
                } else if (("TURBOPACK compile-time value", "development") !== 'production' && typeof console !== 'undefined') {
                    // Old behavior for people using React.PropTypes
                    var cacheKey = componentName + ':' + propName;
                    if (!manualPropTypeCallCache[cacheKey] && // Avoid spamming the console because they are often not actionable except for lib authors
                    manualPropTypeWarningCount < 3) {
                        printWarning('You are manually calling a React.PropTypes validation ' + 'function for the `' + propFullName + '` prop on `' + componentName + '`. This is deprecated ' + 'and will throw in the standalone `prop-types` package. ' + 'You may be seeing this warning due to a third-party PropTypes ' + 'library. See https://fb.me/react-warning-dont-call-proptypes ' + 'for details.');
                        manualPropTypeCallCache[cacheKey] = true;
                        manualPropTypeWarningCount++;
                    }
                }
            }
            if (props[propName] == null) {
                if (isRequired) {
                    if (props[propName] === null) {
                        return new PropTypeError('The ' + location + ' `' + propFullName + '` is marked as required ' + ('in `' + componentName + '`, but its value is `null`.'));
                    }
                    return new PropTypeError('The ' + location + ' `' + propFullName + '` is marked as required in ' + ('`' + componentName + '`, but its value is `undefined`.'));
                }
                return null;
            } else {
                return validate(props, propName, componentName, location, propFullName);
            }
        }
        var chainedCheckType = checkType.bind(null, false);
        chainedCheckType.isRequired = checkType.bind(null, true);
        return chainedCheckType;
    }
    function createPrimitiveTypeChecker(expectedType) {
        function validate(props, propName, componentName, location, propFullName, secret) {
            var propValue = props[propName];
            var propType = getPropType(propValue);
            if (propType !== expectedType) {
                // `propValue` being instance of, say, date/regexp, pass the 'object'
                // check, but we can offer a more precise error message here rather than
                // 'of type `object`'.
                var preciseType = getPreciseType(propValue);
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + preciseType + '` supplied to `' + componentName + '`, expected ') + ('`' + expectedType + '`.'), {
                    expectedType: expectedType
                });
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createAnyTypeChecker() {
        return createChainableTypeChecker(emptyFunctionThatReturnsNull);
    }
    function createArrayOfTypeChecker(typeChecker) {
        function validate(props, propName, componentName, location, propFullName) {
            if (typeof typeChecker !== 'function') {
                return new PropTypeError('Property `' + propFullName + '` of component `' + componentName + '` has invalid PropType notation inside arrayOf.');
            }
            var propValue = props[propName];
            if (!Array.isArray(propValue)) {
                var propType = getPropType(propValue);
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + propType + '` supplied to `' + componentName + '`, expected an array.'));
            }
            for(var i = 0; i < propValue.length; i++){
                var error = typeChecker(propValue, i, componentName, location, propFullName + '[' + i + ']', ReactPropTypesSecret);
                if (error instanceof Error) {
                    return error;
                }
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createElementTypeChecker() {
        function validate(props, propName, componentName, location, propFullName) {
            var propValue = props[propName];
            if (!isValidElement(propValue)) {
                var propType = getPropType(propValue);
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + propType + '` supplied to `' + componentName + '`, expected a single ReactElement.'));
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createElementTypeTypeChecker() {
        function validate(props, propName, componentName, location, propFullName) {
            var propValue = props[propName];
            if (!ReactIs.isValidElementType(propValue)) {
                var propType = getPropType(propValue);
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + propType + '` supplied to `' + componentName + '`, expected a single ReactElement type.'));
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createInstanceTypeChecker(expectedClass) {
        function validate(props, propName, componentName, location, propFullName) {
            if (!(props[propName] instanceof expectedClass)) {
                var expectedClassName = expectedClass.name || ANONYMOUS;
                var actualClassName = getClassName(props[propName]);
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + actualClassName + '` supplied to `' + componentName + '`, expected ') + ('instance of `' + expectedClassName + '`.'));
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createEnumTypeChecker(expectedValues) {
        if (!Array.isArray(expectedValues)) {
            if ("TURBOPACK compile-time truthy", 1) {
                if (arguments.length > 1) {
                    printWarning('Invalid arguments supplied to oneOf, expected an array, got ' + arguments.length + ' arguments. ' + 'A common mistake is to write oneOf(x, y, z) instead of oneOf([x, y, z]).');
                } else {
                    printWarning('Invalid argument supplied to oneOf, expected an array.');
                }
            }
            return emptyFunctionThatReturnsNull;
        }
        function validate(props, propName, componentName, location, propFullName) {
            var propValue = props[propName];
            for(var i = 0; i < expectedValues.length; i++){
                if (is(propValue, expectedValues[i])) {
                    return null;
                }
            }
            var valuesString = JSON.stringify(expectedValues, function replacer(key, value) {
                var type = getPreciseType(value);
                if (type === 'symbol') {
                    return String(value);
                }
                return value;
            });
            return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of value `' + String(propValue) + '` ' + ('supplied to `' + componentName + '`, expected one of ' + valuesString + '.'));
        }
        return createChainableTypeChecker(validate);
    }
    function createObjectOfTypeChecker(typeChecker) {
        function validate(props, propName, componentName, location, propFullName) {
            if (typeof typeChecker !== 'function') {
                return new PropTypeError('Property `' + propFullName + '` of component `' + componentName + '` has invalid PropType notation inside objectOf.');
            }
            var propValue = props[propName];
            var propType = getPropType(propValue);
            if (propType !== 'object') {
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type ' + ('`' + propType + '` supplied to `' + componentName + '`, expected an object.'));
            }
            for(var key in propValue){
                if (has(propValue, key)) {
                    var error = typeChecker(propValue, key, componentName, location, propFullName + '.' + key, ReactPropTypesSecret);
                    if (error instanceof Error) {
                        return error;
                    }
                }
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createUnionTypeChecker(arrayOfTypeCheckers) {
        if (!Array.isArray(arrayOfTypeCheckers)) {
            ("TURBOPACK compile-time truthy", 1) ? printWarning('Invalid argument supplied to oneOfType, expected an instance of array.') : "TURBOPACK unreachable";
            return emptyFunctionThatReturnsNull;
        }
        for(var i = 0; i < arrayOfTypeCheckers.length; i++){
            var checker = arrayOfTypeCheckers[i];
            if (typeof checker !== 'function') {
                printWarning('Invalid argument supplied to oneOfType. Expected an array of check functions, but ' + 'received ' + getPostfixForTypeWarning(checker) + ' at index ' + i + '.');
                return emptyFunctionThatReturnsNull;
            }
        }
        function validate(props, propName, componentName, location, propFullName) {
            var expectedTypes = [];
            for(var i = 0; i < arrayOfTypeCheckers.length; i++){
                var checker = arrayOfTypeCheckers[i];
                var checkerResult = checker(props, propName, componentName, location, propFullName, ReactPropTypesSecret);
                if (checkerResult == null) {
                    return null;
                }
                if (checkerResult.data && has(checkerResult.data, 'expectedType')) {
                    expectedTypes.push(checkerResult.data.expectedType);
                }
            }
            var expectedTypesMessage = expectedTypes.length > 0 ? ', expected one of type [' + expectedTypes.join(', ') + ']' : '';
            return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` supplied to ' + ('`' + componentName + '`' + expectedTypesMessage + '.'));
        }
        return createChainableTypeChecker(validate);
    }
    function createNodeChecker() {
        function validate(props, propName, componentName, location, propFullName) {
            if (!isNode(props[propName])) {
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` supplied to ' + ('`' + componentName + '`, expected a ReactNode.'));
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function invalidValidatorError(componentName, location, propFullName, key, type) {
        return new PropTypeError((componentName || 'React class') + ': ' + location + ' type `' + propFullName + '.' + key + '` is invalid; ' + 'it must be a function, usually from the `prop-types` package, but received `' + type + '`.');
    }
    function createShapeTypeChecker(shapeTypes) {
        function validate(props, propName, componentName, location, propFullName) {
            var propValue = props[propName];
            var propType = getPropType(propValue);
            if (propType !== 'object') {
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type `' + propType + '` ' + ('supplied to `' + componentName + '`, expected `object`.'));
            }
            for(var key in shapeTypes){
                var checker = shapeTypes[key];
                if (typeof checker !== 'function') {
                    return invalidValidatorError(componentName, location, propFullName, key, getPreciseType(checker));
                }
                var error = checker(propValue, key, componentName, location, propFullName + '.' + key, ReactPropTypesSecret);
                if (error) {
                    return error;
                }
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function createStrictShapeTypeChecker(shapeTypes) {
        function validate(props, propName, componentName, location, propFullName) {
            var propValue = props[propName];
            var propType = getPropType(propValue);
            if (propType !== 'object') {
                return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` of type `' + propType + '` ' + ('supplied to `' + componentName + '`, expected `object`.'));
            }
            // We need to check all keys in case some are required but missing from props.
            var allKeys = assign({}, props[propName], shapeTypes);
            for(var key in allKeys){
                var checker = shapeTypes[key];
                if (has(shapeTypes, key) && typeof checker !== 'function') {
                    return invalidValidatorError(componentName, location, propFullName, key, getPreciseType(checker));
                }
                if (!checker) {
                    return new PropTypeError('Invalid ' + location + ' `' + propFullName + '` key `' + key + '` supplied to `' + componentName + '`.' + '\nBad object: ' + JSON.stringify(props[propName], null, '  ') + '\nValid keys: ' + JSON.stringify(Object.keys(shapeTypes), null, '  '));
                }
                var error = checker(propValue, key, componentName, location, propFullName + '.' + key, ReactPropTypesSecret);
                if (error) {
                    return error;
                }
            }
            return null;
        }
        return createChainableTypeChecker(validate);
    }
    function isNode(propValue) {
        switch(typeof propValue){
            case 'number':
            case 'string':
            case 'undefined':
                return true;
            case 'boolean':
                return !propValue;
            case 'object':
                if (Array.isArray(propValue)) {
                    return propValue.every(isNode);
                }
                if (propValue === null || isValidElement(propValue)) {
                    return true;
                }
                var iteratorFn = getIteratorFn(propValue);
                if (iteratorFn) {
                    var iterator = iteratorFn.call(propValue);
                    var step;
                    if (iteratorFn !== propValue.entries) {
                        while(!(step = iterator.next()).done){
                            if (!isNode(step.value)) {
                                return false;
                            }
                        }
                    } else {
                        // Iterator will provide entry [k,v] tuples rather than values.
                        while(!(step = iterator.next()).done){
                            var entry = step.value;
                            if (entry) {
                                if (!isNode(entry[1])) {
                                    return false;
                                }
                            }
                        }
                    }
                } else {
                    return false;
                }
                return true;
            default:
                return false;
        }
    }
    function isSymbol(propType, propValue) {
        // Native Symbol.
        if (propType === 'symbol') {
            return true;
        }
        // falsy value can't be a Symbol
        if (!propValue) {
            return false;
        }
        // 19.4.3.5 Symbol.prototype[@@toStringTag] === 'Symbol'
        if (propValue['@@toStringTag'] === 'Symbol') {
            return true;
        }
        // Fallback for non-spec compliant Symbols which are polyfilled.
        if (typeof Symbol === 'function' && propValue instanceof Symbol) {
            return true;
        }
        return false;
    }
    // Equivalent of `typeof` but with special handling for array and regexp.
    function getPropType(propValue) {
        var propType = typeof propValue;
        if (Array.isArray(propValue)) {
            return 'array';
        }
        if (propValue instanceof RegExp) {
            // Old webkits (at least until Android 4.0) return 'function' rather than
            // 'object' for typeof a RegExp. We'll normalize this here so that /bla/
            // passes PropTypes.object.
            return 'object';
        }
        if (isSymbol(propType, propValue)) {
            return 'symbol';
        }
        return propType;
    }
    // This handles more types than `getPropType`. Only used for error messages.
    // See `createPrimitiveTypeChecker`.
    function getPreciseType(propValue) {
        if (typeof propValue === 'undefined' || propValue === null) {
            return '' + propValue;
        }
        var propType = getPropType(propValue);
        if (propType === 'object') {
            if (propValue instanceof Date) {
                return 'date';
            } else if (propValue instanceof RegExp) {
                return 'regexp';
            }
        }
        return propType;
    }
    // Returns a string that is postfixed to a warning about an invalid type.
    // For example, "undefined" or "of type array"
    function getPostfixForTypeWarning(value) {
        var type = getPreciseType(value);
        switch(type){
            case 'array':
            case 'object':
                return 'an ' + type;
            case 'boolean':
            case 'date':
            case 'regexp':
                return 'a ' + type;
            default:
                return type;
        }
    }
    // Returns class name of the object, if any.
    function getClassName(propValue) {
        if (!propValue.constructor || !propValue.constructor.name) {
            return ANONYMOUS;
        }
        return propValue.constructor.name;
    }
    ReactPropTypes.checkPropTypes = checkPropTypes;
    ReactPropTypes.resetWarningCache = checkPropTypes.resetWarningCache;
    ReactPropTypes.PropTypes = ReactPropTypes;
    return ReactPropTypes;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/**
 * Copyright (c) 2013-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ if ("TURBOPACK compile-time truthy", 1) {
    var ReactIs = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/react-is/index.js [app-client] (ecmascript)");
    // By explicitly using `prop-types` you are opting into new development behavior.
    // http://fb.me/prop-types-in-prod
    var throwOnDirectAccess = true;
    module.exports = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/factoryWithTypeCheckers.js [app-client] (ecmascript)")(ReactIs.isElement, throwOnDirectAccess);
} else //TURBOPACK unreachable
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/ReactPropTypesSecret.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

/**
 * Copyright (c) 2013-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ var ReactPropTypesSecret = 'SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED';
module.exports = ReactPropTypesSecret;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/lib/has.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {

module.exports = Function.call.bind(Object.prototype.hasOwnProperty);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/formats.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RFC1738",
    ()=>RFC1738,
    "RFC3986",
    ()=>RFC3986,
    "default",
    ()=>__TURBOPACK__default__export__,
    "formatters",
    ()=>formatters
]);
'use strict';
const replace = String.prototype.replace;
const percentTwenties = /%20/g;
const Format = {
    RFC1738: 'RFC1738',
    RFC3986: 'RFC3986'
};
const formatters = {
    RFC1738: function(value) {
        return replace.call(value, percentTwenties, '+');
    },
    RFC3986: function(value) {
        return String(value);
    }
};
const RFC1738 = Format.RFC1738;
const RFC3986 = Format.RFC3986;
const __TURBOPACK__default__export__ = Format.RFC3986;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/parse.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "parse",
    ()=>parse
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/utils.js [app-client] (ecmascript)");
'use strict';
;
const has = Object.prototype.hasOwnProperty;
const isArray = Array.isArray;
const defaults = {
    allowDots: false,
    allowEmptyArrays: false,
    allowPrototypes: false,
    allowSparse: false,
    arrayLimit: 20,
    comma: false,
    decodeDotInKeys: false,
    decoder: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["decode"],
    delimiter: '&',
    depth: 5,
    duplicates: 'combine',
    ignoreQueryPrefix: false,
    parameterLimit: 1000,
    parseArrays: true,
    plainObjects: false,
    strictNullHandling: false
};
const parseArrayValue = function(val, options) {
    if (val && typeof val === 'string' && options.comma && val.indexOf(',') > -1) {
        return val.split(',');
    }
    return val;
};
const parseValues = function parseQueryStringValues(str, options) {
    const obj = {
        __proto__: null
    };
    const cleanStr = options.ignoreQueryPrefix ? str.replace(/^\?/, '') : str;
    const limit = options.parameterLimit === Infinity ? undefined : options.parameterLimit;
    const parts = cleanStr.split(options.delimiter, limit);
    let i;
    for(i = 0; i < parts.length; ++i){
        const part = parts[i];
        const bracketEqualsPos = part.indexOf(']=');
        const pos = bracketEqualsPos === -1 ? part.indexOf('=') : bracketEqualsPos + 1;
        let key, val;
        if (pos === -1) {
            key = options.decoder(part, defaults.decoder, 'key');
            val = options.strictNullHandling ? null : '';
        } else {
            key = options.decoder(part.slice(0, pos), defaults.decoder, 'key');
            val = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["maybeMap"](parseArrayValue(part.slice(pos + 1), options), function(encodedVal) {
                return options.decoder(encodedVal, defaults.decoder, 'value');
            });
        }
        if (part.indexOf('[]=') > -1) {
            val = isArray(val) ? [
                val
            ] : val;
        }
        if (options.comma && isArray(val) && val.length > options.arrayLimit) {
            val = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["combine"]([], val, options.arrayLimit, options.plainObjects);
        }
        const existing = has.call(obj, key);
        if (existing && options.duplicates === 'combine') {
            obj[key] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["combine"](obj[key], val, options.arrayLimit, options.plainObjects);
        } else if (!existing || options.duplicates === 'last') {
            obj[key] = val;
        }
    }
    return obj;
};
const parseObject = function(chain, val, options, valuesParsed) {
    let leaf = valuesParsed ? val : parseArrayValue(val, options);
    for(let i = chain.length - 1; i >= 0; --i){
        let obj;
        const root = chain[i];
        if (root === '[]' && options.parseArrays) {
            if (__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isOverflow"](leaf)) {
                // leaf is already an overflow object, preserve it
                obj = leaf;
            } else {
                obj = options.allowEmptyArrays && (leaf === '' || options.strictNullHandling && leaf === null) ? [] : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["combine"]([], leaf, options.arrayLimit, options.plainObjects);
            }
        } else {
            obj = options.plainObjects ? Object.create(null) : {};
            const cleanRoot = root.charAt(0) === '[' && root.charAt(root.length - 1) === ']' ? root.slice(1, -1) : root;
            const decodedRoot = options.decodeDotInKeys ? cleanRoot.replace(/%2E/g, '.') : cleanRoot;
            const index = parseInt(decodedRoot, 10);
            if (!options.parseArrays && decodedRoot === '') {
                obj = {
                    0: leaf
                };
            } else if (!isNaN(index) && root !== decodedRoot && String(index) === decodedRoot && index >= 0 && options.parseArrays && index <= options.arrayLimit) {
                obj = [];
                obj[index] = leaf;
            } else if (decodedRoot !== '__proto__') {
                obj[decodedRoot] = leaf;
            }
        }
        leaf = obj;
    }
    return leaf;
};
const parseKeys = function parseQueryStringKeys(givenKey, val, options, valuesParsed) {
    if (!givenKey) {
        return;
    }
    // Transform dot notation to bracket notation
    const key = options.allowDots ? givenKey.replace(/\.([^.[]+)/g, '[$1]') : givenKey;
    // The regex chunks
    const brackets = /(\[[^[\]]*])/;
    const child = /(\[[^[\]]*])/g;
    // Get the parent
    let segment = options.depth > 0 && brackets.exec(key);
    const parent = segment ? key.slice(0, segment.index) : key;
    // Stash the parent if it exists
    const keys = [];
    if (parent) {
        // If we aren't using plain objects, optionally prefix keys that would overwrite object prototype properties
        if (!options.plainObjects && has.call(Object.prototype, parent)) {
            if (!options.allowPrototypes) {
                return;
            }
        }
        keys.push(parent);
    }
    // Loop through children appending to the array until we hit depth
    let i = 0;
    while(options.depth > 0 && (segment = child.exec(key)) !== null && i < options.depth){
        i += 1;
        if (!options.plainObjects && has.call(Object.prototype, segment[1].slice(1, -1))) {
            if (!options.allowPrototypes) {
                return;
            }
        }
        keys.push(segment[1]);
    }
    // If there's a remainder, just add whatever is left
    if (segment) {
        keys.push('[' + key.slice(segment.index) + ']');
    }
    return parseObject(keys, val, options, valuesParsed);
};
const normalizeParseOptions = function normalizeParseOptions(opts) {
    if (!opts) {
        return defaults;
    }
    if (typeof opts.allowEmptyArrays !== 'undefined' && typeof opts.allowEmptyArrays !== 'boolean') {
        throw new TypeError('`allowEmptyArrays` option can only be `true` or `false`, when provided');
    }
    if (typeof opts.decodeDotInKeys !== 'undefined' && typeof opts.decodeDotInKeys !== 'boolean') {
        throw new TypeError('`decodeDotInKeys` option can only be `true` or `false`, when provided');
    }
    if (opts.decoder !== null && typeof opts.decoder !== 'undefined' && typeof opts.decoder !== 'function') {
        throw new TypeError('Decoder has to be a function.');
    }
    const duplicates = typeof opts.duplicates === 'undefined' ? defaults.duplicates : opts.duplicates;
    if (duplicates !== 'combine' && duplicates !== 'first' && duplicates !== 'last') {
        throw new TypeError('The duplicates option must be either combine, first, or last');
    }
    const allowDots = typeof opts.allowDots === 'undefined' ? opts.decodeDotInKeys === true ? true : defaults.allowDots : !!opts.allowDots;
    return {
        allowDots: allowDots,
        allowEmptyArrays: typeof opts.allowEmptyArrays === 'boolean' ? !!opts.allowEmptyArrays : defaults.allowEmptyArrays,
        allowPrototypes: typeof opts.allowPrototypes === 'boolean' ? opts.allowPrototypes : defaults.allowPrototypes,
        allowSparse: typeof opts.allowSparse === 'boolean' ? opts.allowSparse : defaults.allowSparse,
        arrayLimit: typeof opts.arrayLimit === 'number' ? opts.arrayLimit : defaults.arrayLimit,
        comma: typeof opts.comma === 'boolean' ? opts.comma : defaults.comma,
        decodeDotInKeys: typeof opts.decodeDotInKeys === 'boolean' ? opts.decodeDotInKeys : defaults.decodeDotInKeys,
        decoder: typeof opts.decoder === 'function' ? opts.decoder : defaults.decoder,
        delimiter: typeof opts.delimiter === 'string' || __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isRegExp"](opts.delimiter) ? opts.delimiter : defaults.delimiter,
        // eslint-disable-next-line no-implicit-coercion, no-extra-parens
        depth: typeof opts.depth === 'number' || opts.depth === false ? +opts.depth : defaults.depth,
        duplicates: duplicates,
        ignoreQueryPrefix: opts.ignoreQueryPrefix === true,
        parameterLimit: typeof opts.parameterLimit === 'number' ? opts.parameterLimit : defaults.parameterLimit,
        parseArrays: opts.parseArrays !== false,
        plainObjects: typeof opts.plainObjects === 'boolean' ? opts.plainObjects : defaults.plainObjects,
        strictNullHandling: typeof opts.strictNullHandling === 'boolean' ? opts.strictNullHandling : defaults.strictNullHandling
    };
};
function parse(str, opts) {
    const options = normalizeParseOptions(opts);
    if (str === '' || str === null || typeof str === 'undefined') {
        return options.plainObjects ? Object.create(null) : {};
    }
    const tempObj = typeof str === 'string' ? parseValues(str, options) : str;
    let obj = options.plainObjects ? Object.create(null) : {};
    // Iterate over the keys and setup the new object
    const keys = Object.keys(tempObj);
    for(let i = 0; i < keys.length; ++i){
        const key = keys[i];
        const newObj = parseKeys(key, tempObj[key], options, typeof str === 'string');
        obj = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["merge"](obj, newObj, options);
    }
    if (options.allowSparse === true) {
        return obj;
    }
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["compact"](obj);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/stringify.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "stringify",
    ()=>stringify
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/utils.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/formats.js [app-client] (ecmascript)");
'use strict';
;
;
const has = Object.prototype.hasOwnProperty;
const arrayPrefixGenerators = {
    brackets: function brackets(prefix) {
        return prefix + '[]';
    },
    comma: 'comma',
    indices: function indices(prefix, key) {
        return prefix + '[' + key + ']';
    },
    repeat: function repeat(prefix) {
        return prefix;
    }
};
const isArray = Array.isArray;
const push = Array.prototype.push;
const pushToArray = function(arr, valueOrArray) {
    push.apply(arr, isArray(valueOrArray) ? valueOrArray : [
        valueOrArray
    ]);
};
const toISO = Date.prototype.toISOString;
const defaultFormat = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
const defaults = {
    addQueryPrefix: false,
    allowDots: false,
    allowEmptyArrays: false,
    arrayFormat: 'indices',
    delimiter: '&',
    encode: true,
    encodeDotInKeys: false,
    encoder: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["encode"],
    encodeValuesOnly: false,
    format: defaultFormat,
    formatter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatters"][defaultFormat],
    // deprecated
    indices: false,
    serializeDate: function serializeDate(date) {
        return toISO.call(date);
    },
    skipNulls: false,
    strictNullHandling: false
};
const isNonNullishPrimitive = function isNonNullishPrimitive(v) {
    return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' || typeof v === 'symbol' || typeof v === 'bigint';
};
const sentinel = {};
const _stringify = function stringify(object, prefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, encoder, filter, sort, allowDots, serializeDate, format, formatter, encodeValuesOnly, sideChannel) {
    let obj = object;
    let tmpSc = sideChannel;
    let step = 0;
    let findFlag = false;
    while((tmpSc = tmpSc.get(sentinel)) !== void undefined && !findFlag){
        // Where object last appeared in the ref tree
        const pos = tmpSc.get(object);
        step += 1;
        if (typeof pos !== 'undefined') {
            if (pos === step) {
                throw new RangeError('Cyclic object value');
            } else {
                findFlag = true; // Break while
            }
        }
        if (typeof tmpSc.get(sentinel) === 'undefined') {
            step = 0;
        }
    }
    if (typeof filter === 'function') {
        obj = filter(prefix, obj);
    } else if (obj instanceof Date) {
        obj = serializeDate(obj);
    } else if (generateArrayPrefix === 'comma' && isArray(obj)) {
        obj = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["maybeMap"](obj, function(value) {
            if (value instanceof Date) {
                return serializeDate(value);
            }
            return value;
        });
    }
    if (obj === null) {
        if (strictNullHandling) {
            return encoder && !encodeValuesOnly ? encoder(prefix, defaults.encoder, 'key', format) : prefix;
        }
        obj = '';
    }
    if (isNonNullishPrimitive(obj) || __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isBuffer"](obj)) {
        if (encoder) {
            const keyValue = encodeValuesOnly ? prefix : encoder(prefix, defaults.encoder, 'key', format);
            return [
                formatter(keyValue) + '=' + formatter(encoder(obj, defaults.encoder, 'value', format))
            ];
        }
        return [
            formatter(prefix) + '=' + formatter(String(obj))
        ];
    }
    const values = [];
    if (typeof obj === 'undefined') {
        return values;
    }
    let objKeys;
    if (generateArrayPrefix === 'comma' && isArray(obj)) {
        // we need to join elements in
        if (encodeValuesOnly && encoder) {
            obj = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$utils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["maybeMap"](obj, encoder);
        }
        objKeys = [
            {
                value: obj.length > 0 ? obj.join(',') || null : void undefined
            }
        ];
    } else if (isArray(filter)) {
        objKeys = filter;
    } else {
        const keys = Object.keys(obj);
        objKeys = sort ? keys.sort(sort) : keys;
    }
    const encodedPrefix = encodeDotInKeys ? prefix.replace(/\./g, '%2E') : prefix;
    const adjustedPrefix = commaRoundTrip && isArray(obj) && obj.length === 1 ? encodedPrefix + '[]' : encodedPrefix;
    if (allowEmptyArrays && isArray(obj) && obj.length === 0) {
        return adjustedPrefix + '[]';
    }
    for(let j = 0; j < objKeys.length; ++j){
        const key = objKeys[j];
        const value = typeof key === 'object' && typeof key.value !== 'undefined' ? key.value : obj[key];
        if (skipNulls && value === null) {
            continue;
        }
        const encodedKey = allowDots && encodeDotInKeys ? key.replace(/\./g, '%2E') : key;
        const keyPrefix = isArray(obj) ? typeof generateArrayPrefix === 'function' ? generateArrayPrefix(adjustedPrefix, encodedKey) : adjustedPrefix : adjustedPrefix + (allowDots ? '.' + encodedKey : '[' + encodedKey + ']');
        sideChannel.set(object, step);
        const valueSideChannel = new WeakMap();
        valueSideChannel.set(sentinel, sideChannel);
        pushToArray(values, _stringify(value, keyPrefix, generateArrayPrefix, commaRoundTrip, allowEmptyArrays, strictNullHandling, skipNulls, encodeDotInKeys, generateArrayPrefix === 'comma' && encodeValuesOnly && isArray(obj) ? null : encoder, filter, sort, allowDots, serializeDate, format, formatter, encodeValuesOnly, valueSideChannel));
    }
    return values;
};
const normalizeStringifyOptions = function normalizeStringifyOptions(opts) {
    if (!opts) {
        return defaults;
    }
    if (typeof opts.allowEmptyArrays !== 'undefined' && typeof opts.allowEmptyArrays !== 'boolean') {
        throw new TypeError('`allowEmptyArrays` option can only be `true` or `false`, when provided');
    }
    if (typeof opts.encodeDotInKeys !== 'undefined' && typeof opts.encodeDotInKeys !== 'boolean') {
        throw new TypeError('`encodeDotInKeys` option can only be `true` or `false`, when provided');
    }
    if (opts.encoder !== null && typeof opts.encoder !== 'undefined' && typeof opts.encoder !== 'function') {
        throw new TypeError('Encoder has to be a function.');
    }
    let format = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
    if (typeof opts.format !== 'undefined') {
        if (!has.call(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatters"], opts.format)) {
            throw new TypeError('Unknown format option provided.');
        }
        format = opts.format;
    }
    const formatter = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatters"][format];
    let filter = defaults.filter;
    if (typeof opts.filter === 'function' || isArray(opts.filter)) {
        filter = opts.filter;
    }
    let arrayFormat;
    if (opts.arrayFormat in arrayPrefixGenerators) {
        arrayFormat = opts.arrayFormat;
    } else if ('indices' in opts) {
        arrayFormat = opts.indices ? 'indices' : 'repeat';
    } else {
        arrayFormat = defaults.arrayFormat;
    }
    if ('commaRoundTrip' in opts && typeof opts.commaRoundTrip !== 'boolean') {
        throw new TypeError('`commaRoundTrip` must be a boolean, or absent');
    }
    const allowDots = typeof opts.allowDots === 'undefined' ? opts.encodeDotInKeys === true ? true : defaults.allowDots : !!opts.allowDots;
    return {
        addQueryPrefix: typeof opts.addQueryPrefix === 'boolean' ? opts.addQueryPrefix : defaults.addQueryPrefix,
        allowDots: allowDots,
        allowEmptyArrays: typeof opts.allowEmptyArrays === 'boolean' ? !!opts.allowEmptyArrays : defaults.allowEmptyArrays,
        arrayFormat: arrayFormat,
        commaRoundTrip: opts.commaRoundTrip,
        delimiter: typeof opts.delimiter === 'undefined' ? defaults.delimiter : opts.delimiter,
        encode: typeof opts.encode === 'boolean' ? opts.encode : defaults.encode,
        encodeDotInKeys: typeof opts.encodeDotInKeys === 'boolean' ? opts.encodeDotInKeys : defaults.encodeDotInKeys,
        encoder: typeof opts.encoder === 'function' ? opts.encoder : defaults.encoder,
        encodeValuesOnly: typeof opts.encodeValuesOnly === 'boolean' ? opts.encodeValuesOnly : defaults.encodeValuesOnly,
        filter: filter,
        format: format,
        formatter: formatter,
        serializeDate: typeof opts.serializeDate === 'function' ? opts.serializeDate : defaults.serializeDate,
        skipNulls: typeof opts.skipNulls === 'boolean' ? opts.skipNulls : defaults.skipNulls,
        sort: typeof opts.sort === 'function' ? opts.sort : null,
        strictNullHandling: typeof opts.strictNullHandling === 'boolean' ? opts.strictNullHandling : defaults.strictNullHandling
    };
};
function stringify(object, opts) {
    let obj = object;
    const options = normalizeStringifyOptions(opts);
    let objKeys;
    let filter;
    if (typeof options.filter === 'function') {
        filter = options.filter;
        obj = filter('', obj);
    } else if (isArray(options.filter)) {
        filter = options.filter;
        objKeys = filter;
    }
    const keys = [];
    if (typeof obj !== 'object' || obj === null) {
        return '';
    }
    const generateArrayPrefix = arrayPrefixGenerators[options.arrayFormat];
    const commaRoundTrip = generateArrayPrefix === 'comma' && options.commaRoundTrip;
    if (!objKeys) {
        objKeys = Object.keys(obj);
    }
    if (options.sort) {
        objKeys.sort(options.sort);
    }
    const sideChannel = new WeakMap();
    for(let i = 0; i < objKeys.length; ++i){
        const key = objKeys[i];
        if (options.skipNulls && obj[key] === null) {
            continue;
        }
        pushToArray(keys, _stringify(obj[key], key, generateArrayPrefix, commaRoundTrip, options.allowEmptyArrays, options.strictNullHandling, options.skipNulls, options.encodeDotInKeys, options.encode ? options.encoder : null, options.filter, options.sort, options.allowDots, options.serializeDate, options.format, options.formatter, options.encodeValuesOnly, sideChannel));
    }
    const joined = keys.join(options.delimiter);
    const prefix = options.addQueryPrefix === true ? '?' : '';
    return joined.length > 0 ? prefix + joined : '';
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/utils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "arrayToObject",
    ()=>arrayToObject,
    "assign",
    ()=>assign,
    "combine",
    ()=>combine,
    "compact",
    ()=>compact,
    "decode",
    ()=>decode,
    "encode",
    ()=>encode,
    "isBuffer",
    ()=>isBuffer,
    "isOverflow",
    ()=>isOverflow,
    "isRegExp",
    ()=>isRegExp,
    "maybeMap",
    ()=>maybeMap,
    "merge",
    ()=>merge
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/formats.js [app-client] (ecmascript)");
'use strict';
;
const has = Object.prototype.hasOwnProperty;
const isArray = Array.isArray;
const overflowChannel = new WeakMap();
var markOverflow = function markOverflow(obj, maxIndex) {
    overflowChannel.set(obj, maxIndex);
    return obj;
};
function isOverflow(obj) {
    return overflowChannel.has(obj);
}
var getMaxIndex = function getMaxIndex(obj) {
    return overflowChannel.get(obj);
};
var setMaxIndex = function setMaxIndex(obj, maxIndex) {
    overflowChannel.set(obj, maxIndex);
};
const hexTable = function() {
    const array = [];
    for(let i = 0; i < 256; ++i){
        array.push('%' + ((i < 16 ? '0' : '') + i.toString(16)).toUpperCase());
    }
    return array;
}();
const compactQueue = function compactQueue(queue) {
    while(queue.length > 1){
        const item = queue.pop();
        const obj = item.obj[item.prop];
        if (isArray(obj)) {
            const compacted = [];
            for(let j = 0; j < obj.length; ++j){
                if (typeof obj[j] !== 'undefined') {
                    compacted.push(obj[j]);
                }
            }
            item.obj[item.prop] = compacted;
        }
    }
};
const arrayToObject = function arrayToObject(source, options) {
    const obj = options && options.plainObjects ? Object.create(null) : {};
    for(let i = 0; i < source.length; ++i){
        if (typeof source[i] !== 'undefined') {
            obj[i] = source[i];
        }
    }
    return obj;
};
const merge = function merge(target, source, options) {
    /* eslint no-param-reassign: 0 */ if (!source) {
        return target;
    }
    if (typeof source !== 'object') {
        if (isArray(target)) {
            target.push(source);
        } else if (target && typeof target === 'object') {
            if (isOverflow(target)) {
                // Add at next numeric index for overflow objects
                var newIndex = getMaxIndex(target) + 1;
                target[newIndex] = source;
                setMaxIndex(target, newIndex);
            } else if (options && (options.plainObjects || options.allowPrototypes) || !has.call(Object.prototype, source)) {
                target[source] = true;
            }
        } else {
            return [
                target,
                source
            ];
        }
        return target;
    }
    if (!target || typeof target !== 'object') {
        if (isOverflow(source)) {
            // Create new object with target at 0, source values shifted by 1
            var sourceKeys = Object.keys(source);
            var result = options && options.plainObjects ? {
                __proto__: null,
                0: target
            } : {
                0: target
            };
            for(var m = 0; m < sourceKeys.length; m++){
                var oldKey = parseInt(sourceKeys[m], 10);
                result[oldKey + 1] = source[sourceKeys[m]];
            }
            return markOverflow(result, getMaxIndex(source) + 1);
        }
        return [
            target
        ].concat(source);
    }
    let mergeTarget = target;
    if (isArray(target) && !isArray(source)) {
        mergeTarget = arrayToObject(target, options);
    }
    if (isArray(target) && isArray(source)) {
        source.forEach(function(item, i) {
            if (has.call(target, i)) {
                const targetItem = target[i];
                if (targetItem && typeof targetItem === 'object' && item && typeof item === 'object') {
                    target[i] = merge(targetItem, item, options);
                } else {
                    target.push(item);
                }
            } else {
                target[i] = item;
            }
        });
        return target;
    }
    return Object.keys(source).reduce(function(acc, key) {
        const value = source[key];
        if (has.call(acc, key)) {
            acc[key] = merge(acc[key], value, options);
        } else {
            acc[key] = value;
        }
        return acc;
    }, mergeTarget);
};
const assign = function assignSingleSource(target, source) {
    return Object.keys(source).reduce(function(acc, key) {
        acc[key] = source[key];
        return acc;
    }, target);
};
const decode = function(str) {
    const strWithoutPlus = str.replace(/\+/g, ' ');
    try {
        return decodeURIComponent(strWithoutPlus);
    } catch (e) {
        return strWithoutPlus;
    }
};
const limit = 1024;
const encode = function encode(str, _defaultEncoder, _kind, format) {
    // This code was originally written by Brian White (mscdex) for the io.js core querystring library.
    // It has been adapted here for stricter adherence to RFC 3986
    if (str.length === 0) {
        return str;
    }
    let string = str;
    if (typeof str === 'symbol') {
        string = Symbol.prototype.toString.call(str);
    } else if (typeof str !== 'string') {
        string = String(str);
    }
    let out = '';
    for(let j = 0; j < string.length; j += limit){
        const segment = string.length >= limit ? string.slice(j, j + limit) : string;
        const arr = [];
        for(let i = 0; i < segment.length; ++i){
            let c = segment.charCodeAt(i);
            if (c === 0x2d || // -
            c === 0x2e || // .
            c === 0x5f || // _
            c === 0x7e || c >= 0x30 && c <= 0x39 || c >= 0x41 && c <= 0x5a || c >= 0x61 && c <= 0x7a || format === __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$formats$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RFC1738"] && (c === 0x28 || c === 0x29) // ( )
            ) {
                arr[arr.length] = segment.charAt(i);
                continue;
            }
            if (c < 0x80) {
                arr[arr.length] = hexTable[c];
                continue;
            }
            if (c < 0x800) {
                arr[arr.length] = hexTable[0xc0 | c >> 6] + hexTable[0x80 | c & 0x3f];
                continue;
            }
            if (c < 0xd800 || c >= 0xe000) {
                arr[arr.length] = hexTable[0xe0 | c >> 12] + hexTable[0x80 | c >> 6 & 0x3f] + hexTable[0x80 | c & 0x3f];
                continue;
            }
            i += 1;
            c = 0x10000 + ((c & 0x3ff) << 10 | segment.charCodeAt(i) & 0x3ff);
            arr[arr.length] = hexTable[0xf0 | c >> 18] + hexTable[0x80 | c >> 12 & 0x3f] + hexTable[0x80 | c >> 6 & 0x3f] + hexTable[0x80 | c & 0x3f];
        }
        out += arr.join('');
    }
    return out;
};
const compact = function compact(value) {
    const queue = [
        {
            obj: {
                o: value
            },
            prop: 'o'
        }
    ];
    const refs = [];
    for(let i = 0; i < queue.length; ++i){
        const item = queue[i];
        const obj = item.obj[item.prop];
        const keys = Object.keys(obj);
        for(let j = 0; j < keys.length; ++j){
            const key = keys[j];
            const val = obj[key];
            if (typeof val === 'object' && val !== null && refs.indexOf(val) === -1) {
                queue.push({
                    obj: obj,
                    prop: key
                });
                refs.push(val);
            }
        }
    }
    compactQueue(queue);
    return value;
};
const isRegExp = function isRegExp(obj) {
    return Object.prototype.toString.call(obj) === '[object RegExp]';
};
const isBuffer = function isBuffer(obj) {
    if (!obj || typeof obj !== 'object') {
        return false;
    }
    return !!(obj.constructor && obj.constructor.isBuffer && obj.constructor.isBuffer(obj));
};
const combine = function combine(a, b, arrayLimit, plainObjects) {
    // If 'a' is already an overflow object, add to it
    if (isOverflow(a)) {
        var newIndex = getMaxIndex(a) + 1;
        a[newIndex] = b;
        setMaxIndex(a, newIndex);
        return a;
    }
    var result = [].concat(a, b);
    if (result.length > arrayLimit) {
        return markOverflow(arrayToObject(result, {
            plainObjects: plainObjects
        }), result.length - 1);
    }
    return result;
};
const maybeMap = function maybeMap(val, fn) {
    if (isArray(val)) {
        const mapped = [];
        for(let i = 0; i < val.length; i += 1){
            mapped.push(fn(val[i]));
        }
        return mapped;
    }
    return fn(val);
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-is/cjs/react-is.development.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
/** @license React v16.13.1
 * react-is.development.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */ 'use strict';
if ("TURBOPACK compile-time truthy", 1) {
    (function() {
        'use strict';
        // The Symbol used to tag the ReactElement-like types. If there is no native Symbol
        // nor polyfill, then a plain number is used for performance.
        var hasSymbol = typeof Symbol === 'function' && Symbol.for;
        var REACT_ELEMENT_TYPE = hasSymbol ? Symbol.for('react.element') : 0xeac7;
        var REACT_PORTAL_TYPE = hasSymbol ? Symbol.for('react.portal') : 0xeaca;
        var REACT_FRAGMENT_TYPE = hasSymbol ? Symbol.for('react.fragment') : 0xeacb;
        var REACT_STRICT_MODE_TYPE = hasSymbol ? Symbol.for('react.strict_mode') : 0xeacc;
        var REACT_PROFILER_TYPE = hasSymbol ? Symbol.for('react.profiler') : 0xead2;
        var REACT_PROVIDER_TYPE = hasSymbol ? Symbol.for('react.provider') : 0xeacd;
        var REACT_CONTEXT_TYPE = hasSymbol ? Symbol.for('react.context') : 0xeace; // TODO: We don't use AsyncMode or ConcurrentMode anymore. They were temporary
        // (unstable) APIs that have been removed. Can we remove the symbols?
        var REACT_ASYNC_MODE_TYPE = hasSymbol ? Symbol.for('react.async_mode') : 0xeacf;
        var REACT_CONCURRENT_MODE_TYPE = hasSymbol ? Symbol.for('react.concurrent_mode') : 0xeacf;
        var REACT_FORWARD_REF_TYPE = hasSymbol ? Symbol.for('react.forward_ref') : 0xead0;
        var REACT_SUSPENSE_TYPE = hasSymbol ? Symbol.for('react.suspense') : 0xead1;
        var REACT_SUSPENSE_LIST_TYPE = hasSymbol ? Symbol.for('react.suspense_list') : 0xead8;
        var REACT_MEMO_TYPE = hasSymbol ? Symbol.for('react.memo') : 0xead3;
        var REACT_LAZY_TYPE = hasSymbol ? Symbol.for('react.lazy') : 0xead4;
        var REACT_BLOCK_TYPE = hasSymbol ? Symbol.for('react.block') : 0xead9;
        var REACT_FUNDAMENTAL_TYPE = hasSymbol ? Symbol.for('react.fundamental') : 0xead5;
        var REACT_RESPONDER_TYPE = hasSymbol ? Symbol.for('react.responder') : 0xead6;
        var REACT_SCOPE_TYPE = hasSymbol ? Symbol.for('react.scope') : 0xead7;
        function isValidElementType(type) {
            return typeof type === 'string' || typeof type === 'function' || // Note: its typeof might be other than 'symbol' or 'number' if it's a polyfill.
            type === REACT_FRAGMENT_TYPE || type === REACT_CONCURRENT_MODE_TYPE || type === REACT_PROFILER_TYPE || type === REACT_STRICT_MODE_TYPE || type === REACT_SUSPENSE_TYPE || type === REACT_SUSPENSE_LIST_TYPE || typeof type === 'object' && type !== null && (type.$$typeof === REACT_LAZY_TYPE || type.$$typeof === REACT_MEMO_TYPE || type.$$typeof === REACT_PROVIDER_TYPE || type.$$typeof === REACT_CONTEXT_TYPE || type.$$typeof === REACT_FORWARD_REF_TYPE || type.$$typeof === REACT_FUNDAMENTAL_TYPE || type.$$typeof === REACT_RESPONDER_TYPE || type.$$typeof === REACT_SCOPE_TYPE || type.$$typeof === REACT_BLOCK_TYPE);
        }
        function typeOf(object) {
            if (typeof object === 'object' && object !== null) {
                var $$typeof = object.$$typeof;
                switch($$typeof){
                    case REACT_ELEMENT_TYPE:
                        var type = object.type;
                        switch(type){
                            case REACT_ASYNC_MODE_TYPE:
                            case REACT_CONCURRENT_MODE_TYPE:
                            case REACT_FRAGMENT_TYPE:
                            case REACT_PROFILER_TYPE:
                            case REACT_STRICT_MODE_TYPE:
                            case REACT_SUSPENSE_TYPE:
                                return type;
                            default:
                                var $$typeofType = type && type.$$typeof;
                                switch($$typeofType){
                                    case REACT_CONTEXT_TYPE:
                                    case REACT_FORWARD_REF_TYPE:
                                    case REACT_LAZY_TYPE:
                                    case REACT_MEMO_TYPE:
                                    case REACT_PROVIDER_TYPE:
                                        return $$typeofType;
                                    default:
                                        return $$typeof;
                                }
                        }
                    case REACT_PORTAL_TYPE:
                        return $$typeof;
                }
            }
            return undefined;
        } // AsyncMode is deprecated along with isAsyncMode
        var AsyncMode = REACT_ASYNC_MODE_TYPE;
        var ConcurrentMode = REACT_CONCURRENT_MODE_TYPE;
        var ContextConsumer = REACT_CONTEXT_TYPE;
        var ContextProvider = REACT_PROVIDER_TYPE;
        var Element = REACT_ELEMENT_TYPE;
        var ForwardRef = REACT_FORWARD_REF_TYPE;
        var Fragment = REACT_FRAGMENT_TYPE;
        var Lazy = REACT_LAZY_TYPE;
        var Memo = REACT_MEMO_TYPE;
        var Portal = REACT_PORTAL_TYPE;
        var Profiler = REACT_PROFILER_TYPE;
        var StrictMode = REACT_STRICT_MODE_TYPE;
        var Suspense = REACT_SUSPENSE_TYPE;
        var hasWarnedAboutDeprecatedIsAsyncMode = false; // AsyncMode should be deprecated
        function isAsyncMode(object) {
            {
                if (!hasWarnedAboutDeprecatedIsAsyncMode) {
                    hasWarnedAboutDeprecatedIsAsyncMode = true; // Using console['warn'] to evade Babel and ESLint
                    console['warn']('The ReactIs.isAsyncMode() alias has been deprecated, ' + 'and will be removed in React 17+. Update your code to use ' + 'ReactIs.isConcurrentMode() instead. It has the exact same API.');
                }
            }
            return isConcurrentMode(object) || typeOf(object) === REACT_ASYNC_MODE_TYPE;
        }
        function isConcurrentMode(object) {
            return typeOf(object) === REACT_CONCURRENT_MODE_TYPE;
        }
        function isContextConsumer(object) {
            return typeOf(object) === REACT_CONTEXT_TYPE;
        }
        function isContextProvider(object) {
            return typeOf(object) === REACT_PROVIDER_TYPE;
        }
        function isElement(object) {
            return typeof object === 'object' && object !== null && object.$$typeof === REACT_ELEMENT_TYPE;
        }
        function isForwardRef(object) {
            return typeOf(object) === REACT_FORWARD_REF_TYPE;
        }
        function isFragment(object) {
            return typeOf(object) === REACT_FRAGMENT_TYPE;
        }
        function isLazy(object) {
            return typeOf(object) === REACT_LAZY_TYPE;
        }
        function isMemo(object) {
            return typeOf(object) === REACT_MEMO_TYPE;
        }
        function isPortal(object) {
            return typeOf(object) === REACT_PORTAL_TYPE;
        }
        function isProfiler(object) {
            return typeOf(object) === REACT_PROFILER_TYPE;
        }
        function isStrictMode(object) {
            return typeOf(object) === REACT_STRICT_MODE_TYPE;
        }
        function isSuspense(object) {
            return typeOf(object) === REACT_SUSPENSE_TYPE;
        }
        exports.AsyncMode = AsyncMode;
        exports.ConcurrentMode = ConcurrentMode;
        exports.ContextConsumer = ContextConsumer;
        exports.ContextProvider = ContextProvider;
        exports.Element = Element;
        exports.ForwardRef = ForwardRef;
        exports.Fragment = Fragment;
        exports.Lazy = Lazy;
        exports.Memo = Memo;
        exports.Portal = Portal;
        exports.Profiler = Profiler;
        exports.StrictMode = StrictMode;
        exports.Suspense = Suspense;
        exports.isAsyncMode = isAsyncMode;
        exports.isConcurrentMode = isConcurrentMode;
        exports.isContextConsumer = isContextConsumer;
        exports.isContextProvider = isContextProvider;
        exports.isElement = isElement;
        exports.isForwardRef = isForwardRef;
        exports.isFragment = isFragment;
        exports.isLazy = isLazy;
        exports.isMemo = isMemo;
        exports.isPortal = isPortal;
        exports.isProfiler = isProfiler;
        exports.isStrictMode = isStrictMode;
        exports.isSuspense = isSuspense;
        exports.isValidElementType = isValidElementType;
        exports.typeOf = typeOf;
    })();
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-is/index.js [app-client] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
'use strict';
if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
;
else {
    module.exports = __turbopack_context__.r("[project]/blueprints/payload-next-multisite/app/node_modules/react-is/cjs/react-is.development.js [app-client] (ecmascript)");
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/CSSTransition.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$extends$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/extends.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$objectWithoutPropertiesLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/objectWithoutPropertiesLoose.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$inheritsLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/inheritsLoose.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$addClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/addClass.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$removeClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/dom-helpers/esm/removeClass.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$Transition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/Transition.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$PropTypes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/PropTypes.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$reflow$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/reflow.js [app-client] (ecmascript)");
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
var _addClass = function addClass(node, classes) {
    return node && classes && classes.split(' ').forEach(function(c) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$addClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(node, c);
    });
};
var removeClass = function removeClass(node, classes) {
    return node && classes && classes.split(' ').forEach(function(c) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$dom$2d$helpers$2f$esm$2f$removeClass$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(node, c);
    });
};
/**
 * A transition component inspired by the excellent
 * [ng-animate](https://docs.angularjs.org/api/ngAnimate) library, you should
 * use it if you're using CSS transitions or animations. It's built upon the
 * [`Transition`](https://reactcommunity.org/react-transition-group/transition)
 * component, so it inherits all of its props.
 *
 * `CSSTransition` applies a pair of class names during the `appear`, `enter`,
 * and `exit` states of the transition. The first class is applied and then a
 * second `*-active` class in order to activate the CSS transition. After the
 * transition, matching `*-done` class names are applied to persist the
 * transition state.
 *
 * ```jsx
 * function App() {
 *   const [inProp, setInProp] = useState(false);
 *   return (
 *     <div>
 *       <CSSTransition in={inProp} timeout={200} classNames="my-node">
 *         <div>
 *           {"I'll receive my-node-* classes"}
 *         </div>
 *       </CSSTransition>
 *       <button type="button" onClick={() => setInProp(true)}>
 *         Click to Enter
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 *
 * When the `in` prop is set to `true`, the child component will first receive
 * the class `example-enter`, then the `example-enter-active` will be added in
 * the next tick. `CSSTransition` [forces a
 * reflow](https://github.com/reactjs/react-transition-group/blob/5007303e729a74be66a21c3e2205e4916821524b/src/CSSTransition.js#L208-L215)
 * between before adding the `example-enter-active`. This is an important trick
 * because it allows us to transition between `example-enter` and
 * `example-enter-active` even though they were added immediately one after
 * another. Most notably, this is what makes it possible for us to animate
 * _appearance_.
 *
 * ```css
 * .my-node-enter {
 *   opacity: 0;
 * }
 * .my-node-enter-active {
 *   opacity: 1;
 *   transition: opacity 200ms;
 * }
 * .my-node-exit {
 *   opacity: 1;
 * }
 * .my-node-exit-active {
 *   opacity: 0;
 *   transition: opacity 200ms;
 * }
 * ```
 *
 * `*-active` classes represent which styles you want to animate **to**, so it's
 * important to add `transition` declaration only to them, otherwise transitions
 * might not behave as intended! This might not be obvious when the transitions
 * are symmetrical, i.e. when `*-enter-active` is the same as `*-exit`, like in
 * the example above (minus `transition`), but it becomes apparent in more
 * complex transitions.
 *
 * **Note**: If you're using the
 * [`appear`](http://reactcommunity.org/react-transition-group/transition#Transition-prop-appear)
 * prop, make sure to define styles for `.appear-*` classes as well.
 */ var CSSTransition = /*#__PURE__*/ function(_React$Component) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$inheritsLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(CSSTransition, _React$Component);
    function CSSTransition() {
        var _this;
        for(var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++){
            args[_key] = arguments[_key];
        }
        _this = _React$Component.call.apply(_React$Component, [
            this
        ].concat(args)) || this;
        _this.appliedClasses = {
            appear: {},
            enter: {},
            exit: {}
        };
        _this.onEnter = function(maybeNode, maybeAppearing) {
            var _this$resolveArgument = _this.resolveArguments(maybeNode, maybeAppearing), node = _this$resolveArgument[0], appearing = _this$resolveArgument[1];
            _this.removeClasses(node, 'exit');
            _this.addClass(node, appearing ? 'appear' : 'enter', 'base');
            if (_this.props.onEnter) {
                _this.props.onEnter(maybeNode, maybeAppearing);
            }
        };
        _this.onEntering = function(maybeNode, maybeAppearing) {
            var _this$resolveArgument2 = _this.resolveArguments(maybeNode, maybeAppearing), node = _this$resolveArgument2[0], appearing = _this$resolveArgument2[1];
            var type = appearing ? 'appear' : 'enter';
            _this.addClass(node, type, 'active');
            if (_this.props.onEntering) {
                _this.props.onEntering(maybeNode, maybeAppearing);
            }
        };
        _this.onEntered = function(maybeNode, maybeAppearing) {
            var _this$resolveArgument3 = _this.resolveArguments(maybeNode, maybeAppearing), node = _this$resolveArgument3[0], appearing = _this$resolveArgument3[1];
            var type = appearing ? 'appear' : 'enter';
            _this.removeClasses(node, type);
            _this.addClass(node, type, 'done');
            if (_this.props.onEntered) {
                _this.props.onEntered(maybeNode, maybeAppearing);
            }
        };
        _this.onExit = function(maybeNode) {
            var _this$resolveArgument4 = _this.resolveArguments(maybeNode), node = _this$resolveArgument4[0];
            _this.removeClasses(node, 'appear');
            _this.removeClasses(node, 'enter');
            _this.addClass(node, 'exit', 'base');
            if (_this.props.onExit) {
                _this.props.onExit(maybeNode);
            }
        };
        _this.onExiting = function(maybeNode) {
            var _this$resolveArgument5 = _this.resolveArguments(maybeNode), node = _this$resolveArgument5[0];
            _this.addClass(node, 'exit', 'active');
            if (_this.props.onExiting) {
                _this.props.onExiting(maybeNode);
            }
        };
        _this.onExited = function(maybeNode) {
            var _this$resolveArgument6 = _this.resolveArguments(maybeNode), node = _this$resolveArgument6[0];
            _this.removeClasses(node, 'exit');
            _this.addClass(node, 'exit', 'done');
            if (_this.props.onExited) {
                _this.props.onExited(maybeNode);
            }
        };
        _this.resolveArguments = function(maybeNode, maybeAppearing) {
            return _this.props.nodeRef ? [
                _this.props.nodeRef.current,
                maybeNode
            ] // here `maybeNode` is actually `appearing`
             : [
                maybeNode,
                maybeAppearing
            ];
        };
        _this.getClassNames = function(type) {
            var classNames = _this.props.classNames;
            var isStringClassNames = typeof classNames === 'string';
            var prefix = isStringClassNames && classNames ? classNames + "-" : '';
            var baseClassName = isStringClassNames ? "" + prefix + type : classNames[type];
            var activeClassName = isStringClassNames ? baseClassName + "-active" : classNames[type + "Active"];
            var doneClassName = isStringClassNames ? baseClassName + "-done" : classNames[type + "Done"];
            return {
                baseClassName: baseClassName,
                activeClassName: activeClassName,
                doneClassName: doneClassName
            };
        };
        return _this;
    }
    var _proto = CSSTransition.prototype;
    _proto.addClass = function addClass(node, type, phase) {
        var className = this.getClassNames(type)[phase + "ClassName"];
        var _this$getClassNames = this.getClassNames('enter'), doneClassName = _this$getClassNames.doneClassName;
        if (type === 'appear' && phase === 'done' && doneClassName) {
            className += " " + doneClassName;
        } // This is to force a repaint,
        // which is necessary in order to transition styles when adding a class name.
        if (phase === 'active') {
            if (node) (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$reflow$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forceReflow"])(node);
        }
        if (className) {
            this.appliedClasses[type][phase] = className;
            _addClass(node, className);
        }
    };
    _proto.removeClasses = function removeClasses(node, type) {
        var _this$appliedClasses$ = this.appliedClasses[type], baseClassName = _this$appliedClasses$.base, activeClassName = _this$appliedClasses$.active, doneClassName = _this$appliedClasses$.done;
        this.appliedClasses[type] = {};
        if (baseClassName) {
            removeClass(node, baseClassName);
        }
        if (activeClassName) {
            removeClass(node, activeClassName);
        }
        if (doneClassName) {
            removeClass(node, doneClassName);
        }
    };
    _proto.render = function render() {
        var _this$props = this.props, _ = _this$props.classNames, props = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$objectWithoutPropertiesLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_this$props, [
            "classNames"
        ]);
        return /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$Transition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$extends$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])({}, props, {
            onEnter: this.onEnter,
            onEntered: this.onEntered,
            onEntering: this.onEntering,
            onExit: this.onExit,
            onExiting: this.onExiting,
            onExited: this.onExited
        }));
    };
    return CSSTransition;
}(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
CSSTransition.defaultProps = {
    classNames: ''
};
CSSTransition.propTypes = ("TURBOPACK compile-time truthy", 1) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$extends$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])({}, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$Transition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].propTypes, {
    /**
   * The animation classNames applied to the component as it appears, enters,
   * exits or has finished the transition. A single name can be provided, which
   * will be suffixed for each stage, e.g. `classNames="fade"` applies:
   *
   * - `fade-appear`, `fade-appear-active`, `fade-appear-done`
   * - `fade-enter`, `fade-enter-active`, `fade-enter-done`
   * - `fade-exit`, `fade-exit-active`, `fade-exit-done`
   *
   * A few details to note about how these classes are applied:
   *
   * 1. They are _joined_ with the ones that are already defined on the child
   *    component, so if you want to add some base styles, you can use
   *    `className` without worrying that it will be overridden.
   *
   * 2. If the transition component mounts with `in={false}`, no classes are
   *    applied yet. You might be expecting `*-exit-done`, but if you think
   *    about it, a component cannot finish exiting if it hasn't entered yet.
   *
   * 2. `fade-appear-done` and `fade-enter-done` will _both_ be applied. This
   *    allows you to define different behavior for when appearing is done and
   *    when regular entering is done, using selectors like
   *    `.fade-enter-done:not(.fade-appear-done)`. For example, you could apply
   *    an epic entrance animation when element first appears in the DOM using
   *    [Animate.css](https://daneden.github.io/animate.css/). Otherwise you can
   *    simply use `fade-enter-done` for defining both cases.
   *
   * Each individual classNames can also be specified independently like:
   *
   * ```js
   * classNames={{
   *  appear: 'my-appear',
   *  appearActive: 'my-active-appear',
   *  appearDone: 'my-done-appear',
   *  enter: 'my-enter',
   *  enterActive: 'my-active-enter',
   *  enterDone: 'my-done-enter',
   *  exit: 'my-exit',
   *  exitActive: 'my-active-exit',
   *  exitDone: 'my-done-exit',
   * }}
   * ```
   *
   * If you want to set these classes using CSS Modules:
   *
   * ```js
   * import styles from './styles.css';
   * ```
   *
   * you might want to use camelCase in your CSS file, that way could simply
   * spread them instead of listing them one by one:
   *
   * ```js
   * classNames={{ ...styles }}
   * ```
   *
   * @type {string | {
   *  appear?: string,
   *  appearActive?: string,
   *  appearDone?: string,
   *  enter?: string,
   *  enterActive?: string,
   *  enterDone?: string,
   *  exit?: string,
   *  exitActive?: string,
   *  exitDone?: string,
   * }}
   */ classNames: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$PropTypes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["classNamesShape"],
    /**
   * A `<Transition>` callback fired immediately after the 'enter' or 'appear' class is
   * applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool)
   */ onEnter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * A `<Transition>` callback fired immediately after the 'enter-active' or
   * 'appear-active' class is applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool)
   */ onEntering: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * A `<Transition>` callback fired immediately after the 'enter' or
   * 'appear' classes are **removed** and the `done` class is added to the DOM node.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool)
   */ onEntered: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * A `<Transition>` callback fired immediately after the 'exit' class is
   * applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed
   *
   * @type Function(node: HtmlElement)
   */ onExit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * A `<Transition>` callback fired immediately after the 'exit-active' is applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed
   *
   * @type Function(node: HtmlElement)
   */ onExiting: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * A `<Transition>` callback fired immediately after the 'exit' classes
   * are **removed** and the `exit-done` class is added to the DOM node.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed
   *
   * @type Function(node: HtmlElement)
   */ onExited: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func
}) : "TURBOPACK unreachable";
const __TURBOPACK__default__export__ = CSSTransition;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/CSSTransition.js [app-client] (ecmascript) <export default as CSSTransition>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CSSTransition",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$CSSTransition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$CSSTransition$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/CSSTransition.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/Transition.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ENTERED",
    ()=>ENTERED,
    "ENTERING",
    ()=>ENTERING,
    "EXITED",
    ()=>EXITED,
    "EXITING",
    ()=>EXITING,
    "UNMOUNTED",
    ()=>UNMOUNTED,
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$objectWithoutPropertiesLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/objectWithoutPropertiesLoose.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$inheritsLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@babel/runtime/helpers/esm/inheritsLoose.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react-dom/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$config$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/config.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$PropTypes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/PropTypes.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$TransitionGroupContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/TransitionGroupContext.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$reflow$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/reflow.js [app-client] (ecmascript)");
;
;
;
;
;
;
;
;
;
var UNMOUNTED = 'unmounted';
var EXITED = 'exited';
var ENTERING = 'entering';
var ENTERED = 'entered';
var EXITING = 'exiting';
/**
 * The Transition component lets you describe a transition from one component
 * state to another _over time_ with a simple declarative API. Most commonly
 * it's used to animate the mounting and unmounting of a component, but can also
 * be used to describe in-place transition states as well.
 *
 * ---
 *
 * **Note**: `Transition` is a platform-agnostic base component. If you're using
 * transitions in CSS, you'll probably want to use
 * [`CSSTransition`](https://reactcommunity.org/react-transition-group/css-transition)
 * instead. It inherits all the features of `Transition`, but contains
 * additional features necessary to play nice with CSS transitions (hence the
 * name of the component).
 *
 * ---
 *
 * By default the `Transition` component does not alter the behavior of the
 * component it renders, it only tracks "enter" and "exit" states for the
 * components. It's up to you to give meaning and effect to those states. For
 * example we can add styles to a component when it enters or exits:
 *
 * ```jsx
 * import { Transition } from 'react-transition-group';
 *
 * const duration = 300;
 *
 * const defaultStyle = {
 *   transition: `opacity ${duration}ms ease-in-out`,
 *   opacity: 0,
 * }
 *
 * const transitionStyles = {
 *   entering: { opacity: 1 },
 *   entered:  { opacity: 1 },
 *   exiting:  { opacity: 0 },
 *   exited:  { opacity: 0 },
 * };
 *
 * const Fade = ({ in: inProp }) => (
 *   <Transition in={inProp} timeout={duration}>
 *     {state => (
 *       <div style={{
 *         ...defaultStyle,
 *         ...transitionStyles[state]
 *       }}>
 *         I'm a fade Transition!
 *       </div>
 *     )}
 *   </Transition>
 * );
 * ```
 *
 * There are 4 main states a Transition can be in:
 *  - `'entering'`
 *  - `'entered'`
 *  - `'exiting'`
 *  - `'exited'`
 *
 * Transition state is toggled via the `in` prop. When `true` the component
 * begins the "Enter" stage. During this stage, the component will shift from
 * its current transition state, to `'entering'` for the duration of the
 * transition and then to the `'entered'` stage once it's complete. Let's take
 * the following example (we'll use the
 * [useState](https://reactjs.org/docs/hooks-reference.html#usestate) hook):
 *
 * ```jsx
 * function App() {
 *   const [inProp, setInProp] = useState(false);
 *   return (
 *     <div>
 *       <Transition in={inProp} timeout={500}>
 *         {state => (
 *           // ...
 *         )}
 *       </Transition>
 *       <button onClick={() => setInProp(true)}>
 *         Click to Enter
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 *
 * When the button is clicked the component will shift to the `'entering'` state
 * and stay there for 500ms (the value of `timeout`) before it finally switches
 * to `'entered'`.
 *
 * When `in` is `false` the same thing happens except the state moves from
 * `'exiting'` to `'exited'`.
 */ var Transition = /*#__PURE__*/ function(_React$Component) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$inheritsLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(Transition, _React$Component);
    function Transition(props, context) {
        var _this;
        _this = _React$Component.call(this, props, context) || this;
        var parentGroup = context; // In the context of a TransitionGroup all enters are really appears
        var appear = parentGroup && !parentGroup.isMounting ? props.enter : props.appear;
        var initialStatus;
        _this.appearStatus = null;
        if (props.in) {
            if (appear) {
                initialStatus = EXITED;
                _this.appearStatus = ENTERING;
            } else {
                initialStatus = ENTERED;
            }
        } else {
            if (props.unmountOnExit || props.mountOnEnter) {
                initialStatus = UNMOUNTED;
            } else {
                initialStatus = EXITED;
            }
        }
        _this.state = {
            status: initialStatus
        };
        _this.nextCallback = null;
        return _this;
    }
    Transition.getDerivedStateFromProps = function getDerivedStateFromProps(_ref, prevState) {
        var nextIn = _ref.in;
        if (nextIn && prevState.status === UNMOUNTED) {
            return {
                status: EXITED
            };
        }
        return null;
    } // getSnapshotBeforeUpdate(prevProps) {
    ;
    var _proto = Transition.prototype;
    _proto.componentDidMount = function componentDidMount() {
        this.updateStatus(true, this.appearStatus);
    };
    _proto.componentDidUpdate = function componentDidUpdate(prevProps) {
        var nextStatus = null;
        if (prevProps !== this.props) {
            var status = this.state.status;
            if (this.props.in) {
                if (status !== ENTERING && status !== ENTERED) {
                    nextStatus = ENTERING;
                }
            } else {
                if (status === ENTERING || status === ENTERED) {
                    nextStatus = EXITING;
                }
            }
        }
        this.updateStatus(false, nextStatus);
    };
    _proto.componentWillUnmount = function componentWillUnmount() {
        this.cancelNextCallback();
    };
    _proto.getTimeouts = function getTimeouts() {
        var timeout = this.props.timeout;
        var exit, enter, appear;
        exit = enter = appear = timeout;
        if (timeout != null && typeof timeout !== 'number') {
            exit = timeout.exit;
            enter = timeout.enter; // TODO: remove fallback for next major
            appear = timeout.appear !== undefined ? timeout.appear : enter;
        }
        return {
            exit: exit,
            enter: enter,
            appear: appear
        };
    };
    _proto.updateStatus = function updateStatus(mounting, nextStatus) {
        if (mounting === void 0) {
            mounting = false;
        }
        if (nextStatus !== null) {
            // nextStatus will always be ENTERING or EXITING.
            this.cancelNextCallback();
            if (nextStatus === ENTERING) {
                if (this.props.unmountOnExit || this.props.mountOnEnter) {
                    var node = this.props.nodeRef ? this.props.nodeRef.current : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].findDOMNode(this); // https://github.com/reactjs/react-transition-group/pull/749
                    // With unmountOnExit or mountOnEnter, the enter animation should happen at the transition between `exited` and `entering`.
                    // To make the animation happen,  we have to separate each rendering and avoid being processed as batched.
                    if (node) (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$reflow$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["forceReflow"])(node);
                }
                this.performEnter(mounting);
            } else {
                this.performExit();
            }
        } else if (this.props.unmountOnExit && this.state.status === EXITED) {
            this.setState({
                status: UNMOUNTED
            });
        }
    };
    _proto.performEnter = function performEnter(mounting) {
        var _this2 = this;
        var enter = this.props.enter;
        var appearing = this.context ? this.context.isMounting : mounting;
        var _ref2 = this.props.nodeRef ? [
            appearing
        ] : [
            __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].findDOMNode(this),
            appearing
        ], maybeNode = _ref2[0], maybeAppearing = _ref2[1];
        var timeouts = this.getTimeouts();
        var enterTimeout = appearing ? timeouts.appear : timeouts.enter; // no enter animation skip right to ENTERED
        // if we are mounting and running this it means appear _must_ be set
        if (!mounting && !enter || __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$config$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].disabled) {
            this.safeSetState({
                status: ENTERED
            }, function() {
                _this2.props.onEntered(maybeNode);
            });
            return;
        }
        this.props.onEnter(maybeNode, maybeAppearing);
        this.safeSetState({
            status: ENTERING
        }, function() {
            _this2.props.onEntering(maybeNode, maybeAppearing);
            _this2.onTransitionEnd(enterTimeout, function() {
                _this2.safeSetState({
                    status: ENTERED
                }, function() {
                    _this2.props.onEntered(maybeNode, maybeAppearing);
                });
            });
        });
    };
    _proto.performExit = function performExit() {
        var _this3 = this;
        var exit = this.props.exit;
        var timeouts = this.getTimeouts();
        var maybeNode = this.props.nodeRef ? undefined : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].findDOMNode(this); // no exit animation skip right to EXITED
        if (!exit || __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$config$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].disabled) {
            this.safeSetState({
                status: EXITED
            }, function() {
                _this3.props.onExited(maybeNode);
            });
            return;
        }
        this.props.onExit(maybeNode);
        this.safeSetState({
            status: EXITING
        }, function() {
            _this3.props.onExiting(maybeNode);
            _this3.onTransitionEnd(timeouts.exit, function() {
                _this3.safeSetState({
                    status: EXITED
                }, function() {
                    _this3.props.onExited(maybeNode);
                });
            });
        });
    };
    _proto.cancelNextCallback = function cancelNextCallback() {
        if (this.nextCallback !== null) {
            this.nextCallback.cancel();
            this.nextCallback = null;
        }
    };
    _proto.safeSetState = function safeSetState(nextState, callback) {
        // This shouldn't be necessary, but there are weird race conditions with
        // setState callbacks and unmounting in testing, so always make sure that
        // we can cancel any pending setState callbacks after we unmount.
        callback = this.setNextCallback(callback);
        this.setState(nextState, callback);
    };
    _proto.setNextCallback = function setNextCallback(callback) {
        var _this4 = this;
        var active = true;
        this.nextCallback = function(event) {
            if (active) {
                active = false;
                _this4.nextCallback = null;
                callback(event);
            }
        };
        this.nextCallback.cancel = function() {
            active = false;
        };
        return this.nextCallback;
    };
    _proto.onTransitionEnd = function onTransitionEnd(timeout, handler) {
        this.setNextCallback(handler);
        var node = this.props.nodeRef ? this.props.nodeRef.current : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].findDOMNode(this);
        var doesNotHaveTimeoutOrListener = timeout == null && !this.props.addEndListener;
        if (!node || doesNotHaveTimeoutOrListener) {
            setTimeout(this.nextCallback, 0);
            return;
        }
        if (this.props.addEndListener) {
            var _ref3 = this.props.nodeRef ? [
                this.nextCallback
            ] : [
                node,
                this.nextCallback
            ], maybeNode = _ref3[0], maybeNextCallback = _ref3[1];
            this.props.addEndListener(maybeNode, maybeNextCallback);
        }
        if (timeout != null) {
            setTimeout(this.nextCallback, timeout);
        }
    };
    _proto.render = function render() {
        var status = this.state.status;
        if (status === UNMOUNTED) {
            return null;
        }
        var _this$props = this.props, children = _this$props.children, _in = _this$props.in, _mountOnEnter = _this$props.mountOnEnter, _unmountOnExit = _this$props.unmountOnExit, _appear = _this$props.appear, _enter = _this$props.enter, _exit = _this$props.exit, _timeout = _this$props.timeout, _addEndListener = _this$props.addEndListener, _onEnter = _this$props.onEnter, _onEntering = _this$props.onEntering, _onEntered = _this$props.onEntered, _onExit = _this$props.onExit, _onExiting = _this$props.onExiting, _onExited = _this$props.onExited, _nodeRef = _this$props.nodeRef, childProps = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$babel$2f$runtime$2f$helpers$2f$esm$2f$objectWithoutPropertiesLoose$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(_this$props, [
            "children",
            "in",
            "mountOnEnter",
            "unmountOnExit",
            "appear",
            "enter",
            "exit",
            "timeout",
            "addEndListener",
            "onEnter",
            "onEntering",
            "onEntered",
            "onExit",
            "onExiting",
            "onExited",
            "nodeRef"
        ]);
        return(/*#__PURE__*/ // allows for nested Transitions
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$TransitionGroupContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Provider, {
            value: null
        }, typeof children === 'function' ? children(status, childProps) : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].cloneElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Children.only(children), childProps)));
    };
    return Transition;
}(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Component);
Transition.contextType = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$TransitionGroupContext$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"];
Transition.propTypes = ("TURBOPACK compile-time truthy", 1) ? {
    /**
   * A React reference to DOM element that need to transition:
   * https://stackoverflow.com/a/51127130/4671932
   *
   *   - When `nodeRef` prop is used, `node` is not passed to callback functions
   *      (e.g. `onEnter`) because user already has direct access to the node.
   *   - When changing `key` prop of `Transition` in a `TransitionGroup` a new
   *     `nodeRef` need to be provided to `Transition` with changed `key` prop
   *     (see
   *     [test/CSSTransition-test.js](https://github.com/reactjs/react-transition-group/blob/13435f897b3ab71f6e19d724f145596f5910581c/test/CSSTransition-test.js#L362-L437)).
   */ nodeRef: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].shape({
        current: typeof Element === 'undefined' ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].any : function(propValue, key, componentName, location, propFullName, secret) {
            var value = propValue[key];
            return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].instanceOf(value && 'ownerDocument' in value ? value.ownerDocument.defaultView.Element : Element)(propValue, key, componentName, location, propFullName, secret);
        }
    }),
    /**
   * A `function` child can be used instead of a React element. This function is
   * called with the current transition status (`'entering'`, `'entered'`,
   * `'exiting'`, `'exited'`), which can be used to apply context
   * specific props to a component.
   *
   * ```jsx
   * <Transition in={this.state.in} timeout={150}>
   *   {state => (
   *     <MyComponent className={`fade fade-${state}`} />
   *   )}
   * </Transition>
   * ```
   */ children: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].oneOfType([
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func.isRequired,
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].element.isRequired
    ]).isRequired,
    /**
   * Show the component; triggers the enter or exit states
   */ in: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * By default the child component is mounted immediately along with
   * the parent `Transition` component. If you want to "lazy mount" the component on the
   * first `in={true}` you can set `mountOnEnter`. After the first enter transition the component will stay
   * mounted, even on "exited", unless you also specify `unmountOnExit`.
   */ mountOnEnter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * By default the child component stays mounted after it reaches the `'exited'` state.
   * Set `unmountOnExit` if you'd prefer to unmount the component after it finishes exiting.
   */ unmountOnExit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * By default the child component does not perform the enter transition when
   * it first mounts, regardless of the value of `in`. If you want this
   * behavior, set both `appear` and `in` to `true`.
   *
   * > **Note**: there are no special appear states like `appearing`/`appeared`, this prop
   * > only adds an additional enter transition. However, in the
   * > `<CSSTransition>` component that first enter transition does result in
   * > additional `.appear-*` classes, that way you can choose to style it
   * > differently.
   */ appear: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * Enable or disable enter transitions.
   */ enter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * Enable or disable exit transitions.
   */ exit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].bool,
    /**
   * The duration of the transition, in milliseconds.
   * Required unless `addEndListener` is provided.
   *
   * You may specify a single timeout for all transitions:
   *
   * ```jsx
   * timeout={500}
   * ```
   *
   * or individually:
   *
   * ```jsx
   * timeout={{
   *  appear: 500,
   *  enter: 300,
   *  exit: 500,
   * }}
   * ```
   *
   * - `appear` defaults to the value of `enter`
   * - `enter` defaults to `0`
   * - `exit` defaults to `0`
   *
   * @type {number | { enter?: number, exit?: number, appear?: number }}
   */ timeout: function timeout(props) {
        var pt = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$react$2d$transition$2d$group$2f$esm$2f$utils$2f$PropTypes$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["timeoutsShape"];
        if (!props.addEndListener) pt = pt.isRequired;
        for(var _len = arguments.length, args = new Array(_len > 1 ? _len - 1 : 0), _key = 1; _key < _len; _key++){
            args[_key - 1] = arguments[_key];
        }
        return pt.apply(void 0, [
            props
        ].concat(args));
    },
    /**
   * Add a custom transition end trigger. Called with the transitioning
   * DOM node and a `done` callback. Allows for more fine grained transition end
   * logic. Timeouts are still used as a fallback if provided.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * ```jsx
   * addEndListener={(node, done) => {
   *   // use the css transitionend event to mark the finish of a transition
   *   node.addEventListener('transitionend', done, false);
   * }}
   * ```
   */ addEndListener: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired before the "entering" status is applied. An extra parameter
   * `isAppearing` is supplied to indicate if the enter stage is occurring on the initial mount
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool) -> void
   */ onEnter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired after the "entering" status is applied. An extra parameter
   * `isAppearing` is supplied to indicate if the enter stage is occurring on the initial mount
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool)
   */ onEntering: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired after the "entered" status is applied. An extra parameter
   * `isAppearing` is supplied to indicate if the enter stage is occurring on the initial mount
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement, isAppearing: bool) -> void
   */ onEntered: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired before the "exiting" status is applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement) -> void
   */ onExit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired after the "exiting" status is applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed.
   *
   * @type Function(node: HtmlElement) -> void
   */ onExiting: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func,
    /**
   * Callback fired after the "exited" status is applied.
   *
   * **Note**: when `nodeRef` prop is passed, `node` is not passed
   *
   * @type Function(node: HtmlElement) -> void
   */ onExited: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].func
} : "TURBOPACK unreachable"; // Name the function so it is clearer in the documentation
function noop() {}
Transition.defaultProps = {
    in: false,
    mountOnEnter: false,
    unmountOnExit: false,
    appear: false,
    enter: true,
    exit: true,
    onEnter: noop,
    onEntering: noop,
    onEntered: noop,
    onExit: noop,
    onExiting: noop,
    onExited: noop
};
Transition.UNMOUNTED = UNMOUNTED;
Transition.EXITED = EXITED;
Transition.ENTERING = ENTERING;
Transition.ENTERED = ENTERED;
Transition.EXITING = EXITING;
const __TURBOPACK__default__export__ = Transition;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/TransitionGroupContext.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
const __TURBOPACK__default__export__ = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createContext(null);
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/config.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
const __TURBOPACK__default__export__ = {
    disabled: false
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/PropTypes.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "classNamesShape",
    ()=>classNamesShape,
    "timeoutsShape",
    ()=>timeoutsShape
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$build$2f$polyfills$2f$process$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = /*#__PURE__*/ __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/build/polyfills/process.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/prop-types/index.js [app-client] (ecmascript)");
;
var timeoutsShape = ("TURBOPACK compile-time truthy", 1) ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].oneOfType([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].number,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].shape({
        enter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].number,
        exit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].number,
        appear: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].number
    }).isRequired
]) : "TURBOPACK unreachable";
var classNamesShape = ("TURBOPACK compile-time truthy", 1) ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].oneOfType([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].shape({
        enter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        exit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        active: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string
    }),
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].shape({
        enter: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        enterDone: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        enterActive: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        exit: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        exitDone: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string,
        exitActive: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$prop$2d$types$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].string
    })
]) : "TURBOPACK unreachable";
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/react-transition-group/esm/utils/reflow.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "forceReflow",
    ()=>forceReflow
]);
var forceReflow = function forceReflow(node) {
    return node.scrollTop;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/tabbable/dist/index.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "focusable",
    ()=>focusable,
    "getTabIndex",
    ()=>getTabIndex,
    "isFocusable",
    ()=>isFocusable,
    "isTabbable",
    ()=>isTabbable,
    "tabbable",
    ()=>tabbable
]);
/*!
* tabbable 6.5.0
* @license MIT, https://github.com/focus-trap/tabbable/blob/master/LICENSE
*/ // NOTE: separate `:not()` selectors has broader browser support than the newer
//  `:not([inert], [inert] *)` (Feb 2023)
var candidateSelectors = [
    'input:not([inert]):not([inert] *)',
    'select:not([inert]):not([inert] *)',
    'textarea:not([inert]):not([inert] *)',
    'a[href]:not([inert]):not([inert] *)',
    'area[href]:not([inert]):not([inert] *)',
    'button:not([inert]):not([inert] *)',
    '[tabindex]:not(slot):not([inert]):not([inert] *)',
    'audio[controls]:not([inert]):not([inert] *)',
    'video[controls]:not([inert]):not([inert] *)',
    '[contenteditable]:not([contenteditable="false"]):not([inert]):not([inert] *)',
    'details>summary:first-of-type:not([inert]):not([inert] *)',
    'details:not([inert]):not([inert] *)'
];
var candidateSelector = /* #__PURE__ */ candidateSelectors.join(',');
var NoElement = typeof Element === 'undefined';
var matches = NoElement ? function() {} : Element.prototype.matches || Element.prototype.msMatchesSelector || Element.prototype.webkitMatchesSelector;
var getRootNode = !NoElement && Element.prototype.getRootNode ? function(element) {
    var _element$getRootNode;
    return element === null || element === void 0 ? void 0 : (_element$getRootNode = element.getRootNode) === null || _element$getRootNode === void 0 ? void 0 : _element$getRootNode.call(element);
} : function(element) {
    return element === null || element === void 0 ? void 0 : element.ownerDocument;
};
/**
 * Determines if a node is inert or in an inert ancestor.
 * @param {Node} [node]
 * @param {boolean} [lookUp] If true and `node` is not inert, looks up at ancestors to
 *  see if any of them are inert. If false, only `node` itself is considered.
 * @returns {boolean} True if inert itself or by way of being in an inert ancestor.
 *  False if `node` is falsy.
 */ var _isInert = function isInert(node, lookUp) {
    var _node$getAttribute;
    if (lookUp === void 0) {
        lookUp = true;
    }
    // CAREFUL: JSDom does not support inert at all, so we can't use the `HTMLElement.inert`
    //  JS API property; we have to check the attribute, which can either be empty or 'true';
    //  if it's `null` (not specified) or 'false', it's an active element
    var inertAtt = node === null || node === void 0 ? void 0 : (_node$getAttribute = node.getAttribute) === null || _node$getAttribute === void 0 ? void 0 : _node$getAttribute.call(node, 'inert');
    var inert = inertAtt === '' || inertAtt === 'true';
    // NOTE: this could also be handled with `node.matches('[inert], :is([inert] *)')`
    //  if it weren't for `matches()` not being a function on shadow roots; the following
    //  code works for any kind of node
    var result = inert || lookUp && node && (// closest does not exist on shadow roots, so we fall back to a manual
    // lookup upward, in case it is not defined.
    typeof node.closest === 'function' ? node.closest('[inert]') : _isInert(node.parentNode));
    return result;
};
/**
 * Determines if a node's content is editable.
 * @param {Element} [node]
 * @returns True if it's content-editable; false if it's not or `node` is falsy.
 */ var isContentEditable = function isContentEditable(node) {
    var _node$getAttribute2;
    // CAREFUL: JSDom does not support the `HTMLElement.isContentEditable` API so we have
    //  to use the attribute directly to check for this, which can either be empty or 'true';
    //  if it's `null` (not specified) or 'false', it's a non-editable element
    var attValue = node === null || node === void 0 ? void 0 : (_node$getAttribute2 = node.getAttribute) === null || _node$getAttribute2 === void 0 ? void 0 : _node$getAttribute2.call(node, 'contenteditable');
    return attValue === '' || attValue === 'true';
};
/**
 * @param {Element} el container to check in
 * @param {boolean} includeContainer add container to check
 * @param {(node: Element) => boolean} filter filter candidates
 * @returns {Element[]}
 */ var getCandidates = function getCandidates(el, includeContainer, filter) {
    // even if `includeContainer=false`, we still have to check it for inertness because
    //  if it's inert (either by itself or via its parent), then all its children are inert
    if (_isInert(el)) {
        return [];
    }
    var candidates = Array.prototype.slice.apply(el.querySelectorAll(candidateSelector));
    if (includeContainer && matches.call(el, candidateSelector)) {
        candidates.unshift(el);
    }
    candidates = candidates.filter(filter);
    return candidates;
};
/**
 * @callback GetShadowRoot
 * @param {Element} element to check for shadow root
 * @returns {ShadowRoot|boolean} ShadowRoot if available or boolean indicating if a shadowRoot is attached but not available.
 */ /**
 * @callback ShadowRootFilter
 * @param {Element} shadowHostNode the element which contains shadow content
 * @returns {boolean} true if a shadow root could potentially contain valid candidates.
 */ /**
 * @typedef {Object} CandidateScope
 * @property {Element} scopeParent contains inner candidates
 * @property {Element[]} candidates list of candidates found in the scope parent
 */ /**
 * @typedef {Object} IterativeOptions
 * @property {GetShadowRoot|boolean} getShadowRoot true if shadow support is enabled; falsy if not;
 *  if a function, implies shadow support is enabled and either returns the shadow root of an element
 *  or a boolean stating if it has an undisclosed shadow root
 * @property {(node: Element) => boolean} filter filter candidates
 * @property {boolean} flatten if true then result will flatten any CandidateScope into the returned list
 * @property {ShadowRootFilter} shadowRootFilter filter shadow roots;
 */ /**
 * @param {Element[]} elements list of element containers to match candidates from
 * @param {boolean} includeContainer add container list to check
 * @param {IterativeOptions} options
 * @returns {Array.<Element|CandidateScope>}
 */ var _getCandidatesIteratively = function getCandidatesIteratively(elements, includeContainer, options) {
    var candidates = [];
    var elementsToCheck = Array.from(elements);
    while(elementsToCheck.length){
        var element = elementsToCheck.shift();
        if (_isInert(element, false)) {
            continue;
        }
        if (element.tagName === 'SLOT') {
            // add shadow dom slot scope (slot itself cannot be focusable)
            var assigned = element.assignedElements();
            var content = assigned.length ? assigned : element.children;
            var nestedCandidates = _getCandidatesIteratively(content, true, options);
            if (options.flatten) {
                candidates.push.apply(candidates, nestedCandidates);
            } else {
                candidates.push({
                    scopeParent: element,
                    candidates: nestedCandidates
                });
            }
        } else {
            // check candidate element
            var validCandidate = matches.call(element, candidateSelector);
            if (validCandidate && options.filter(element) && (includeContainer || !elements.includes(element))) {
                candidates.push(element);
            }
            // iterate over shadow content if possible
            var shadowRoot = element.shadowRoot || // check for an undisclosed shadow
            typeof options.getShadowRoot === 'function' && options.getShadowRoot(element);
            // no inert look up because we're already drilling down and checking for inertness
            //  on the way down, so all containers to this root node should have already been
            //  vetted as non-inert
            var validShadowRoot = !_isInert(shadowRoot, false) && (!options.shadowRootFilter || options.shadowRootFilter(element));
            if (shadowRoot && validShadowRoot) {
                // add shadow dom scope IIF a shadow root node was given; otherwise, an undisclosed
                //  shadow exists, so look at light dom children as fallback BUT create a scope for any
                //  child candidates found because they're likely slotted elements (elements that are
                //  children of the web component element (which has the shadow), in the light dom, but
                //  slotted somewhere _inside_ the undisclosed shadow) -- the scope is created below,
                //  _after_ we return from this recursive call
                var _nestedCandidates = _getCandidatesIteratively(shadowRoot === true ? element.children : shadowRoot.children, true, options);
                if (options.flatten) {
                    candidates.push.apply(candidates, _nestedCandidates);
                } else {
                    candidates.push({
                        scopeParent: element,
                        candidates: _nestedCandidates
                    });
                }
            } else {
                // there's not shadow so just dig into the element's (light dom) children
                //  __without__ giving the element special scope treatment
                elementsToCheck.unshift.apply(elementsToCheck, element.children);
            }
        }
    }
    return candidates;
};
/**
 * @private
 * Determines if the node has an explicitly specified `tabindex` attribute.
 * @param {HTMLElement} node
 * @returns {boolean} True if so; false if not.
 */ var hasTabIndex = function hasTabIndex(node) {
    return !isNaN(parseInt(node.getAttribute('tabindex'), 10));
};
/**
 * Determine the tab index of a given node.
 * @param {HTMLElement} node
 * @returns {number} Tab order (negative, 0, or positive number).
 * @throws {Error} If `node` is falsy.
 */ var getTabIndex = function getTabIndex(node) {
    if (!node) {
        throw new Error('No node provided');
    }
    if (node.tabIndex < 0) {
        // in Chrome, <details/>, <audio controls/> and <video controls/> elements get a default
        // `tabIndex` of -1 when the 'tabindex' attribute isn't specified in the DOM,
        // yet they are still part of the regular tab order; in FF, they get a default
        // `tabIndex` of 0; since Chrome still puts those elements in the regular tab
        // order, consider their tab index to be 0.
        // Also browsers do not return `tabIndex` correctly for contentEditable nodes;
        // so if they don't have a tabindex attribute specifically set, assume it's 0.
        if ((/^(AUDIO|VIDEO|DETAILS)$/.test(node.tagName) || isContentEditable(node)) && !hasTabIndex(node)) {
            return 0;
        }
    }
    return node.tabIndex;
};
/**
 * Determine the tab index of a given node __for sort order purposes__.
 * @param {HTMLElement} node
 * @param {boolean} [isScope] True for a custom element with shadow root or slot that, by default,
 *  has tabIndex -1, but needs to be sorted by document order in order for its content to be
 *  inserted into the correct sort position.
 * @returns {number} Tab order (negative, 0, or positive number).
 */ var getSortOrderTabIndex = function getSortOrderTabIndex(node, isScope) {
    var tabIndex = getTabIndex(node);
    if (tabIndex < 0 && isScope && !hasTabIndex(node)) {
        return 0;
    }
    return tabIndex;
};
var sortOrderedTabbables = function sortOrderedTabbables(a, b) {
    return a.tabIndex === b.tabIndex ? a.documentOrder - b.documentOrder : a.tabIndex - b.tabIndex;
};
var isInput = function isInput(node) {
    return node.tagName === 'INPUT';
};
var isHiddenInput = function isHiddenInput(node) {
    return isInput(node) && node.type === 'hidden';
};
var isDetailsWithSummary = function isDetailsWithSummary(node) {
    var r = node.tagName === 'DETAILS' && Array.prototype.slice.apply(node.children).some(function(child) {
        return child.tagName === 'SUMMARY';
    });
    return r;
};
var getCheckedRadio = function getCheckedRadio(nodes, form) {
    for(var i = 0; i < nodes.length; i++){
        if (nodes[i].checked && nodes[i].form === form) {
            return nodes[i];
        }
    }
};
var isTabbableRadio = function isTabbableRadio(node) {
    if (!node.name) {
        return true;
    }
    var radioScope = node.form || getRootNode(node);
    var queryRadios = function queryRadios(name) {
        return radioScope.querySelectorAll('input[type="radio"][name="' + name + '"]');
    };
    var radioSet;
    if (typeof window !== 'undefined' && typeof window.CSS !== 'undefined' && typeof window.CSS.escape === 'function') {
        radioSet = queryRadios(window.CSS.escape(node.name));
    } else {
        try {
            radioSet = queryRadios(node.name);
        } catch (err) {
            // eslint-disable-next-line no-console
            console.error('Looks like you have a radio button with a name attribute containing invalid CSS selector characters and need the CSS.escape polyfill: %s', err.message);
            return false;
        }
    }
    var checked = getCheckedRadio(radioSet, node.form);
    return !checked || checked === node;
};
var isRadio = function isRadio(node) {
    return isInput(node) && node.type === 'radio';
};
var isNonTabbableRadio = function isNonTabbableRadio(node) {
    return isRadio(node) && !isTabbableRadio(node);
};
// determines if a node is ultimately attached to the window's document
var isNodeAttached = function isNodeAttached(node) {
    var _nodeRoot;
    // The root node is the shadow root if the node is in a shadow DOM; some document otherwise
    //  (but NOT _the_ document; see second 'If' comment below for more).
    // If rootNode is shadow root, it'll have a host, which is the element to which the shadow
    //  is attached, and the one we need to check if it's in the document or not (because the
    //  shadow, and all nodes it contains, is never considered in the document since shadows
    //  behave like self-contained DOMs; but if the shadow's HOST, which is part of the document,
    //  is hidden, or is not in the document itself but is detached, it will affect the shadow's
    //  visibility, including all the nodes it contains). The host could be any normal node,
    //  or a custom element (i.e. web component). Either way, that's the one that is considered
    //  part of the document, not the shadow root, nor any of its children (i.e. the node being
    //  tested).
    // To further complicate things, we have to look all the way up until we find a shadow HOST
    //  that is attached (or find none) because the node might be in nested shadows...
    // If rootNode is not a shadow root, it won't have a host, and so rootNode should be the
    //  document (per the docs) and while it's a Document-type object, that document does not
    //  appear to be the same as the node's `ownerDocument` for some reason, so it's safer
    //  to ignore the rootNode at this point, and use `node.ownerDocument`. Otherwise,
    //  using `rootNode.contains(node)` will _always_ be true we'll get false-positives when
    //  node is actually detached.
    // NOTE: If `nodeRootHost` or `node` happens to be the `document` itself (which is possible
    //  if a tabbable/focusable node was quickly added to the DOM, focused, and then removed
    //  from the DOM as in https://github.com/focus-trap/focus-trap-react/issues/905), then
    //  `ownerDocument` will be `null`, hence the optional chaining on it.
    var nodeRoot = node && getRootNode(node);
    var nodeRootHost = (_nodeRoot = nodeRoot) === null || _nodeRoot === void 0 ? void 0 : _nodeRoot.host;
    // in some cases, a detached node will return itself as the root instead of a document or
    //  shadow root object, in which case, we shouldn't try to look further up the host chain
    var attached = false;
    if (nodeRoot && nodeRoot !== node) {
        var _nodeRootHost, _nodeRootHost$ownerDo, _node$ownerDocument;
        attached = !!((_nodeRootHost = nodeRootHost) !== null && _nodeRootHost !== void 0 && (_nodeRootHost$ownerDo = _nodeRootHost.ownerDocument) !== null && _nodeRootHost$ownerDo !== void 0 && _nodeRootHost$ownerDo.contains(nodeRootHost) || node !== null && node !== void 0 && (_node$ownerDocument = node.ownerDocument) !== null && _node$ownerDocument !== void 0 && _node$ownerDocument.contains(node));
        while(!attached && nodeRootHost){
            var _nodeRoot2, _nodeRootHost2, _nodeRootHost2$ownerD;
            // since it's not attached and we have a root host, the node MUST be in a nested shadow DOM,
            //  which means we need to get the host's host and check if that parent host is contained
            //  in (i.e. attached to) the document
            nodeRoot = getRootNode(nodeRootHost);
            nodeRootHost = (_nodeRoot2 = nodeRoot) === null || _nodeRoot2 === void 0 ? void 0 : _nodeRoot2.host;
            attached = !!((_nodeRootHost2 = nodeRootHost) !== null && _nodeRootHost2 !== void 0 && (_nodeRootHost2$ownerD = _nodeRootHost2.ownerDocument) !== null && _nodeRootHost2$ownerD !== void 0 && _nodeRootHost2$ownerD.contains(nodeRootHost));
        }
    }
    return attached;
};
var isZeroArea = function isZeroArea(node) {
    var _node$getBoundingClie = node.getBoundingClientRect(), width = _node$getBoundingClie.width, height = _node$getBoundingClie.height;
    return width === 0 && height === 0;
};
var isHidden = function isHidden(node, _ref) {
    var displayCheck = _ref.displayCheck, getShadowRoot = _ref.getShadowRoot;
    if (displayCheck === 'full-native') {
        if ('checkVisibility' in node) {
            // Chrome >= 105, Edge >= 105, Firefox >= 106, Safari >= 17.4
            // @see https://developer.mozilla.org/en-US/docs/Web/API/Element/checkVisibility#browser_compatibility
            var visible = node.checkVisibility({
                // Checking opacity might be desirable for some use cases, but natively,
                // opacity zero elements _are_ focusable and tabbable.
                checkOpacity: false,
                opacityProperty: false,
                contentVisibilityAuto: true,
                visibilityProperty: true,
                // This is an alias for `visibilityProperty`. Contemporary browsers
                // support both. However, this alias has wider browser support (Chrome
                // >= 105 and Firefox >= 106, vs. Chrome >= 121 and Firefox >= 122), so
                // we include it anyway.
                checkVisibilityCSS: true
            });
            return !visible;
        }
    // Fall through to manual visibility checks
    }
    // NOTE: visibility will be `undefined` if node is detached from the document
    //  (see notes about this further down), which means we will consider it visible
    //  (this is legacy behavior from a very long way back)
    // NOTE: we check this regardless of `displayCheck="none"` because this is a
    //  _visibility_ check, not a _display_ check
    var _getComputedStyle = getComputedStyle(node), visibility = _getComputedStyle.visibility;
    if (visibility === 'hidden' || visibility === 'collapse') {
        return true;
    }
    var isDirectSummary = matches.call(node, 'details>summary:first-of-type');
    var nodeUnderDetails = isDirectSummary ? node.parentElement : node;
    if (matches.call(nodeUnderDetails, 'details:not([open]) *')) {
        return true;
    }
    if (!displayCheck || displayCheck === 'full' || // full-native can run this branch when it falls through in case
    // Element#checkVisibility is unsupported
    displayCheck === 'full-native' || displayCheck === 'legacy-full') {
        if (typeof getShadowRoot === 'function') {
            // figure out if we should consider the node to be in an undisclosed shadow and use the
            //  'non-zero-area' fallback
            var originalNode = node;
            while(node){
                var parentElement = node.parentElement;
                var rootNode = getRootNode(node);
                if (parentElement && !parentElement.shadowRoot && getShadowRoot(parentElement) === true // check if there's an undisclosed shadow
                ) {
                    // node has an undisclosed shadow which means we can only treat it as a black box, so we
                    //  fall back to a non-zero-area test
                    return isZeroArea(node);
                } else if (node.assignedSlot) {
                    // iterate up slot
                    node = node.assignedSlot;
                } else if (!parentElement && rootNode !== node.ownerDocument) {
                    // cross shadow boundary
                    node = rootNode.host;
                } else {
                    // iterate up normal dom
                    node = parentElement;
                }
            }
            node = originalNode;
        }
        // else, `getShadowRoot` might be true, but all that does is enable shadow DOM support
        //  (i.e. it does not also presume that all nodes might have undisclosed shadows); or
        //  it might be a falsy value, which means shadow DOM support is disabled
        // Since we didn't find it sitting in an undisclosed shadow (or shadows are disabled)
        //  now we can just test to see if it would normally be visible or not, provided it's
        //  attached to the main document.
        // NOTE: We must consider case where node is inside a shadow DOM and given directly to
        //  `isTabbable()` or `isFocusable()` -- regardless of `getShadowRoot` option setting.
        if (isNodeAttached(node)) {
            // this works wherever the node is: if there's at least one client rect, it's
            //  somehow displayed; it also covers the CSS 'display: contents' case where the
            //  node itself is hidden in place of its contents; and there's no need to search
            //  up the hierarchy either
            return !node.getClientRects().length;
        }
        // Else, the node isn't attached to the document, which means the `getClientRects()`
        //  API will __always__ return zero rects (this can happen, for example, if React
        //  is used to render nodes onto a detached tree, as confirmed in this thread:
        //  https://github.com/facebook/react/issues/9117#issuecomment-284228870)
        //
        // It also means that even window.getComputedStyle(node).display will return `undefined`
        //  because styles are only computed for nodes that are in the document.
        //
        // NOTE: THIS HAS BEEN THE CASE FOR YEARS. It is not new, nor is it caused by tabbable
        //  somehow. Though it was never stated officially, anyone who has ever used tabbable
        //  APIs on nodes in detached containers has actually implicitly used tabbable in what
        //  was later (as of v5.2.0 on Apr 9, 2021) called `displayCheck="none"` mode -- essentially
        //  considering __everything__ to be visible because of the innability to determine styles.
        //
        // v6.0.0: As of this major release, the default 'full' option __no longer treats detached
        //  nodes as visible with the 'none' fallback.__
        if (displayCheck !== 'legacy-full') {
            return true; // hidden
        }
    // else, fallback to 'none' mode and consider the node visible
    } else if (displayCheck === 'non-zero-area') {
        // NOTE: Even though this tests that the node's client rect is non-zero to determine
        //  whether it's displayed, and that a detached node will __always__ have a zero-area
        //  client rect, we don't special-case for whether the node is attached or not. In
        //  this mode, we do want to consider nodes that have a zero area to be hidden at all
        //  times, and that includes attached or not.
        return isZeroArea(node);
    }
    // visible, as far as we can tell, or per current `displayCheck=none` mode, we assume
    //  it's visible
    return false;
};
// form fields (nested) inside a disabled fieldset are not focusable/tabbable
//  unless they are in the _first_ <legend> element of the top-most disabled
//  fieldset
var isDisabledFromFieldset = function isDisabledFromFieldset(node) {
    if (/^(INPUT|BUTTON|SELECT|TEXTAREA)$/.test(node.tagName)) {
        var parentNode = node.parentElement;
        // check if `node` is contained in a disabled <fieldset>
        while(parentNode){
            if (parentNode.tagName === 'FIELDSET' && parentNode.disabled) {
                // look for the first <legend> among the children of the disabled <fieldset>
                for(var i = 0; i < parentNode.children.length; i++){
                    var child = parentNode.children.item(i);
                    // when the first <legend> (in document order) is found
                    if (child.tagName === 'LEGEND') {
                        // if its parent <fieldset> is not nested in another disabled <fieldset>,
                        // return whether `node` is a descendant of its first <legend>
                        return matches.call(parentNode, 'fieldset[disabled] *') ? true : !child.contains(node);
                    }
                }
                // the disabled <fieldset> containing `node` has no <legend>
                return true;
            }
            parentNode = parentNode.parentElement;
        }
    }
    // else, node's tabbable/focusable state should not be affected by a fieldset's
    //  enabled/disabled state
    return false;
};
var isNodeMatchingSelectorFocusable = function isNodeMatchingSelectorFocusable(options, node) {
    if (node.disabled || isHiddenInput(node) || isHidden(node, options) || // For a details element with a summary, the summary element gets the focus
    isDetailsWithSummary(node) || isDisabledFromFieldset(node)) {
        return false;
    }
    return true;
};
var isNodeMatchingSelectorTabbable = function isNodeMatchingSelectorTabbable(options, node) {
    if (isNonTabbableRadio(node) || getTabIndex(node) < 0 || !isNodeMatchingSelectorFocusable(options, node)) {
        return false;
    }
    return true;
};
var isShadowRootTabbable = function isShadowRootTabbable(shadowHostNode) {
    var tabIndex = parseInt(shadowHostNode.getAttribute('tabindex'), 10);
    if (isNaN(tabIndex) || tabIndex >= 0) {
        return true;
    }
    // If a custom element has an explicit negative tabindex,
    // browsers will not allow tab targeting said element's children.
    return false;
};
/**
 * @param {Array.<Element|CandidateScope>} candidates
 * @returns Element[]
 */ var _sortByOrder = function sortByOrder(candidates) {
    var regularTabbables = [];
    var orderedTabbables = [];
    candidates.forEach(function(item, i) {
        var isScope = !!item.scopeParent;
        var element = isScope ? item.scopeParent : item;
        var candidateTabindex = getSortOrderTabIndex(element, isScope);
        var elements = isScope ? _sortByOrder(item.candidates) : element;
        if (candidateTabindex === 0) {
            isScope ? regularTabbables.push.apply(regularTabbables, elements) : regularTabbables.push(element);
        } else {
            orderedTabbables.push({
                documentOrder: i,
                tabIndex: candidateTabindex,
                item: item,
                isScope: isScope,
                content: elements
            });
        }
    });
    return orderedTabbables.sort(sortOrderedTabbables).reduce(function(acc, sortable) {
        sortable.isScope ? acc.push.apply(acc, sortable.content) : acc.push(sortable.content);
        return acc;
    }, []).concat(regularTabbables);
};
var tabbable = function tabbable(container, options) {
    options = options || {};
    var candidates;
    if (options.getShadowRoot) {
        candidates = _getCandidatesIteratively([
            container
        ], options.includeContainer, {
            filter: isNodeMatchingSelectorTabbable.bind(null, options),
            flatten: false,
            getShadowRoot: options.getShadowRoot,
            shadowRootFilter: isShadowRootTabbable
        });
    } else {
        candidates = getCandidates(container, options.includeContainer, isNodeMatchingSelectorTabbable.bind(null, options));
    }
    return _sortByOrder(candidates);
};
var focusable = function focusable(container, options) {
    options = options || {};
    var candidates;
    if (options.getShadowRoot) {
        candidates = _getCandidatesIteratively([
            container
        ], options.includeContainer, {
            filter: isNodeMatchingSelectorFocusable.bind(null, options),
            flatten: true,
            getShadowRoot: options.getShadowRoot
        });
    } else {
        candidates = getCandidates(container, options.includeContainer, isNodeMatchingSelectorFocusable.bind(null, options));
    }
    return candidates;
};
var isTabbable = function isTabbable(node, options) {
    options = options || {};
    if (!node) {
        throw new Error('No node provided');
    }
    if (matches.call(node, candidateSelector) === false) {
        return false;
    }
    return isNodeMatchingSelectorTabbable(options, node);
};
var focusableCandidateSelector = /* #__PURE__ */ candidateSelectors.concat('iframe:not([inert]):not([inert] *)').join(',');
var isFocusable = function isFocusable(node, options) {
    options = options || {};
    if (!node) {
        throw new Error('No node provided');
    }
    if (matches.call(node, focusableCandidateSelector) === false) {
        return false;
    }
    return isNodeMatchingSelectorFocusable(options, node);
};
;
}),
]);

//# sourceMappingURL=0nrf_06cndjb._.js.map