module.exports = [
"[externals]/@payloadcms/db-postgres [external] (@payloadcms/db-postgres, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/db-postgres)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
var mod = await __turbopack_context__.y("@payloadcms/db-postgres-46e6ec01e94abf2e");

__turbopack_context__.n(mod);
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, true);}),
"[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
var mod = await __turbopack_context__.y("payload-c4b6786c0743b3eb");

__turbopack_context__.n(mod);
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, true);}),
"[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
var mod = await __turbopack_context__.y("payload-c4b6786c0743b3eb/shared");

__turbopack_context__.n(mod);
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, true);}),
"[externals]/sharp [external] (sharp, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/sharp)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
var mod = await __turbopack_context__.y("sharp-92e309043e73f11c");

__turbopack_context__.n(mod);
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, true);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/clipboard/LexicalClipboard.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$generateJSONFromSelectedNodes",
    ()=>$generateJSONFromSelectedNodes,
    "$generateNodesFromSerializedNodes",
    ()=>$generateNodesFromSerializedNodes,
    "$getClipboardDataFromSelection",
    ()=>$getClipboardDataFromSelection,
    "$getHtmlContent",
    ()=>$getHtmlContent,
    "$getLexicalContent",
    ()=>$getLexicalContent,
    "$insertDataTransferForPlainText",
    ()=>$insertDataTransferForPlainText,
    "$insertDataTransferForRichText",
    ()=>$insertDataTransferForRichText,
    "$insertGeneratedNodes",
    ()=>$insertGeneratedNodes,
    "copyToClipboard",
    ()=>copyToClipboard,
    "setLexicalClipboardDataTransfer",
    ()=>setLexicalClipboardDataTransfer
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$html$2f$LexicalHtml$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/html/LexicalHtml.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/utils/LexicalUtils.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
;
;
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ // Do not require this module directly! Use normal `invariant` calls.
function formatDevErrorMessage(message) {
    throw new Error(message);
}
/**
 * Returns the *currently selected* Lexical content as an HTML string, relying on the
 * logic defined in the exportDOM methods on the LexicalNode classes. Note that
 * this will not return the HTML content of the entire editor (unless all the content is included
 * in the current selection).
 *
 * @param editor - LexicalEditor instance to get HTML content from
 * @param selection - The selection to use (default is $getSelection())
 * @returns a string of HTML content
 */ function $getHtmlContent(editor, selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])()) {
    if (selection == null) {
        {
            formatDevErrorMessage(`Expected valid LexicalSelection`);
        }
    }
    // If we haven't selected anything
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed() || selection.getNodes().length === 0) {
        return '';
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$html$2f$LexicalHtml$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$generateHtmlFromNodes"])(editor, selection);
}
/**
 * Returns the *currently selected* Lexical content as a JSON string, relying on the
 * logic defined in the exportJSON methods on the LexicalNode classes. Note that
 * this will not return the JSON content of the entire editor (unless all the content is included
 * in the current selection).
 *
 * @param editor  - LexicalEditor instance to get the JSON content from
 * @param selection - The selection to use (default is $getSelection())
 * @returns
 */ function $getLexicalContent(editor, selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])()) {
    if (selection == null) {
        {
            formatDevErrorMessage(`Expected valid LexicalSelection`);
        }
    }
    // If we haven't selected anything
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed() || selection.getNodes().length === 0) {
        return null;
    }
    return JSON.stringify($generateJSONFromSelectedNodes(editor, selection));
}
/**
 * Attempts to insert content of the mime-types text/plain or text/uri-list from
 * the provided DataTransfer object into the editor at the provided selection.
 * text/uri-list is only used if text/plain is not also provided.
 *
 * @param dataTransfer an object conforming to the [DataTransfer interface] (https://html.spec.whatwg.org/multipage/dnd.html#the-datatransfer-interface)
 * @param selection the selection to use as the insertion point for the content in the DataTransfer object
 */ function $insertDataTransferForPlainText(dataTransfer, selection) {
    const text = dataTransfer.getData('text/plain') || dataTransfer.getData('text/uri-list');
    if (text != null) {
        selection.insertRawText(text);
    }
}
/**
 * Attempts to insert content of the mime-types application/x-lexical-editor, text/html,
 * text/plain, or text/uri-list (in descending order of priority) from the provided DataTransfer
 * object into the editor at the provided selection.
 *
 * @param dataTransfer an object conforming to the [DataTransfer interface] (https://html.spec.whatwg.org/multipage/dnd.html#the-datatransfer-interface)
 * @param selection the selection to use as the insertion point for the content in the DataTransfer object
 * @param editor the LexicalEditor the content is being inserted into.
 */ function $insertDataTransferForRichText(dataTransfer, selection, editor) {
    const lexicalString = dataTransfer.getData('application/x-lexical-editor');
    if (lexicalString) {
        try {
            const payload = JSON.parse(lexicalString);
            if (payload.namespace === editor._config.namespace && Array.isArray(payload.nodes)) {
                const nodes = $generateNodesFromSerializedNodes(payload.nodes);
                return $insertGeneratedNodes(editor, nodes, selection);
            }
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error(error);
        }
    }
    const htmlString = dataTransfer.getData('text/html');
    const plainString = dataTransfer.getData('text/plain');
    // Skip HTML handling if it matches the plain text representation.
    // This avoids unnecessary processing for plain text strings created by
    // iOS Safari autocorrect, which incorrectly includes a `text/html` type.
    if (htmlString && plainString !== htmlString) {
        try {
            const parser = new DOMParser();
            const dom = parser.parseFromString(trustHTML(htmlString), 'text/html');
            const nodes = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$html$2f$LexicalHtml$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$generateNodesFromDOM"])(editor, dom);
            return $insertGeneratedNodes(editor, nodes, selection);
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error(error);
        }
    }
    // Multi-line plain text in rich text mode pasted as separate paragraphs
    // instead of single paragraph with linebreaks.
    // Webkit-specific: Supports read 'text/uri-list' in clipboard.
    const text = plainString || dataTransfer.getData('text/uri-list');
    if (text != null) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            const parts = text.split(/(\r?\n|\t)/);
            if (parts[parts.length - 1] === '') {
                parts.pop();
            }
            for(let i = 0; i < parts.length; i++){
                const currentSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(currentSelection)) {
                    const part = parts[i];
                    if (part === '\n' || part === '\r\n') {
                        currentSelection.insertParagraph();
                    } else if (part === '\t') {
                        currentSelection.insertNodes([
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createTabNode"])()
                        ]);
                    } else {
                        currentSelection.insertText(part);
                    }
                }
            }
        } else {
            selection.insertRawText(text);
        }
    }
}
function trustHTML(html) {
    if (window.trustedTypes && window.trustedTypes.createPolicy) {
        const policy = window.trustedTypes.createPolicy('lexical', {
            createHTML: (input)=>input
        });
        return policy.createHTML(html);
    }
    return html;
}
/**
 * Inserts Lexical nodes into the editor using different strategies depending on
 * some simple selection-based heuristics. If you're looking for a generic way to
 * to insert nodes into the editor at a specific selection point, you probably want
 * {@link lexical.$insertNodes}
 *
 * @param editor LexicalEditor instance to insert the nodes into.
 * @param nodes The nodes to insert.
 * @param selection The selection to insert the nodes into.
 */ function $insertGeneratedNodes(editor, nodes, selection) {
    if (!editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SELECTION_INSERT_CLIPBOARD_NODES_COMMAND"], {
        nodes,
        selection
    })) {
        selection.insertNodes(nodes);
        $updateSelectionOnInsert(selection);
    }
    return;
}
function $updateSelectionOnInsert(selection) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed()) {
        const anchor = selection.anchor;
        let nodeToInspect = null;
        const anchorCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$caretFromPoint"])(anchor, 'previous');
        if (anchorCaret) {
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextPointCaret"])(anchorCaret)) {
                nodeToInspect = anchorCaret.origin;
            } else {
                const range = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getCaretRange"])(anchorCaret, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])(), 'next').getFlipped());
                for (const caret of range){
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(caret.origin)) {
                        nodeToInspect = caret.origin;
                        break;
                    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(caret.origin) && !caret.origin.isInline()) {
                        break;
                    }
                }
            }
        }
        if (nodeToInspect && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(nodeToInspect)) {
            const newFormat = nodeToInspect.getFormat();
            const newStyle = nodeToInspect.getStyle();
            if (selection.format !== newFormat || selection.style !== newStyle) {
                selection.format = newFormat;
                selection.style = newStyle;
                selection.dirty = true;
            }
        }
    }
}
function exportNodeToJSON(node) {
    const serializedNode = node.exportJSON();
    const nodeClass = node.constructor;
    if (serializedNode.type !== nodeClass.getType()) {
        {
            formatDevErrorMessage(`LexicalNode: Node ${nodeClass.name} does not implement .exportJSON().`);
        }
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node)) {
        const serializedChildren = serializedNode.children;
        if (!Array.isArray(serializedChildren)) {
            {
                formatDevErrorMessage(`LexicalNode: Node ${nodeClass.name} is an element but .exportJSON() does not have a children array.`);
            }
        }
    }
    return serializedNode;
}
function $appendNodesToJSON(editor, selection, currentNode, targetArray = []) {
    let shouldInclude = selection !== null ? currentNode.isSelected(selection) : true;
    const shouldExclude = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode) && currentNode.excludeFromCopy('html');
    let target = currentNode;
    if (selection !== null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(target)) {
        target = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$sliceSelectedTextNodeContent"])(selection, target, 'clone');
    }
    const children = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(target) ? target.getChildren() : [];
    const serializedNode = exportNodeToJSON(target);
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(target) && target.getTextContentSize() === 0) {
        // If an uncollapsed selection ends or starts at the end of a line of specialized,
        // TextNodes, such as code tokens, we will get a 'blank' TextNode here, i.e., one
        // with text of length 0. We don't want this, it makes a confusing mess. Reset!
        shouldInclude = false;
    }
    for(let i = 0; i < children.length; i++){
        const childNode = children[i];
        const shouldIncludeChild = $appendNodesToJSON(editor, selection, childNode, serializedNode.children);
        if (!shouldInclude && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode) && shouldIncludeChild && currentNode.extractWithChild(childNode, selection, 'clone')) {
            shouldInclude = true;
        }
    }
    if (shouldInclude && !shouldExclude) {
        targetArray.push(serializedNode);
    } else if (Array.isArray(serializedNode.children)) {
        for(let i = 0; i < serializedNode.children.length; i++){
            const serializedChildNode = serializedNode.children[i];
            targetArray.push(serializedChildNode);
        }
    }
    return shouldInclude;
}
// TODO why $ function with Editor instance?
/**
 * Gets the Lexical JSON of the nodes inside the provided Selection.
 *
 * @param editor LexicalEditor to get the JSON content from.
 * @param selection Selection to get the JSON content from.
 * @returns an object with the editor namespace and a list of serializable nodes as JavaScript objects.
 */ function $generateJSONFromSelectedNodes(editor, selection) {
    const nodes = [];
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])();
    const topLevelChildren = root.getChildren();
    for(let i = 0; i < topLevelChildren.length; i++){
        const topLevelNode = topLevelChildren[i];
        $appendNodesToJSON(editor, selection, topLevelNode, nodes);
    }
    return {
        namespace: editor._config.namespace,
        nodes
    };
}
/**
 * This method takes an array of objects conforming to the BaseSerializedNode interface and returns
 * an Array containing instances of the corresponding LexicalNode classes registered on the editor.
 * Normally, you'd get an Array of BaseSerialized nodes from {@link $generateJSONFromSelectedNodes}
 *
 * @param serializedNodes an Array of objects conforming to the BaseSerializedNode interface.
 * @returns an Array of Lexical Node objects.
 */ function $generateNodesFromSerializedNodes(serializedNodes) {
    const nodes = [];
    for(let i = 0; i < serializedNodes.length; i++){
        const serializedNode = serializedNodes[i];
        const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$parseSerializedNode"])(serializedNode);
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(node)) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$addNodeStyle"])(node);
        }
        nodes.push(node);
    }
    return nodes;
}
const EVENT_LATENCY = 50;
let clipboardEventTimeout = null;
// TODO custom selection
// TODO potentially have a node customizable version for plain text
/**
 * Copies the content of the current selection to the clipboard in
 * text/plain, text/html, and application/x-lexical-editor (Lexical JSON)
 * formats.
 *
 * @param editor the LexicalEditor instance to copy content from
 * @param event the native browser ClipboardEvent to add the content to.
 * @returns
 */ async function copyToClipboard(editor, event, data) {
    if (clipboardEventTimeout !== null) {
        // Prevent weird race conditions that can happen when this function is run multiple times
        // synchronously. In the future, we can do better, we can cancel/override the previously running job.
        return false;
    }
    if (event !== null) {
        return new Promise((resolve, reject)=>{
            editor.update(()=>{
                resolve($copyToClipboardEvent(editor, event, data));
            });
        });
    }
    const rootElement = editor.getRootElement();
    const editorWindow = editor._window || window;
    const windowDocument = editorWindow.document;
    const domSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getDOMSelection"])(editorWindow);
    if (rootElement === null || domSelection === null) {
        return false;
    }
    const element = windowDocument.createElement('span');
    element.style.cssText = 'position: fixed; top: -1000px;';
    element.append(windowDocument.createTextNode('#'));
    rootElement.append(element);
    const range = new Range();
    range.setStart(element, 0);
    range.setEnd(element, 1);
    domSelection.removeAllRanges();
    domSelection.addRange(range);
    return new Promise((resolve, reject)=>{
        const removeListener = editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COPY_COMMAND"], (secondEvent)=>{
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(secondEvent, ClipboardEvent)) {
                removeListener();
                if (clipboardEventTimeout !== null) {
                    editorWindow.clearTimeout(clipboardEventTimeout);
                    clipboardEventTimeout = null;
                }
                resolve($copyToClipboardEvent(editor, secondEvent, data));
            }
            // Block the entire copy flow while we wait for the next ClipboardEvent
            return true;
        }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_CRITICAL"]);
        // If the above hack execCommand hack works, this timeout code should never fire. Otherwise,
        // the listener will be quickly freed so that the user can reuse it again
        clipboardEventTimeout = editorWindow.setTimeout(()=>{
            removeListener();
            clipboardEventTimeout = null;
            resolve(false);
        }, EVENT_LATENCY);
        windowDocument.execCommand('copy');
        element.remove();
    });
}
// TODO shouldn't pass editor (pass namespace directly)
function $copyToClipboardEvent(editor, event, data) {
    if (data === undefined) {
        const domSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getDOMSelection"])(editor._window);
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!selection || selection.isCollapsed()) {
            return false;
        }
        if (!domSelection) {
            return false;
        }
        const anchorDOM = domSelection.anchorNode;
        const focusDOM = domSelection.focusNode;
        if (anchorDOM !== null && focusDOM !== null && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isSelectionWithinEditor"])(editor, anchorDOM, focusDOM)) {
            return false;
        }
        data = $getClipboardDataFromSelection(selection);
    }
    event.preventDefault();
    const clipboardData = event.clipboardData;
    if (clipboardData === null) {
        return false;
    }
    setLexicalClipboardDataTransfer(clipboardData, data);
    return true;
}
const clipboardDataFunctions = [
    [
        'text/html',
        $getHtmlContent
    ],
    [
        'application/x-lexical-editor',
        $getLexicalContent
    ]
];
/**
 * Serialize the content of the current selection to strings in
 * text/plain, text/html, and application/x-lexical-editor (Lexical JSON)
 * formats (as available).
 *
 * @param selection the selection to serialize (defaults to $getSelection())
 * @returns LexicalClipboardData
 */ function $getClipboardDataFromSelection(selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])()) {
    const clipboardData = {
        'text/plain': selection ? selection.getTextContent() : ''
    };
    if (selection) {
        const editor = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getEditor"])();
        for (const [mimeType, $editorFn] of clipboardDataFunctions){
            const v = $editorFn(editor, selection);
            if (v !== null) {
                clipboardData[mimeType] = v;
            }
        }
    }
    return clipboardData;
}
/**
 * Call setData on the given clipboardData for each MIME type present
 * in the given data (from {@link $getClipboardDataFromSelection})
 *
 * @param clipboardData the event.clipboardData to populate from data
 * @param data The lexical data
 */ function setLexicalClipboardDataTransfer(clipboardData, data) {
    for (const [k] of clipboardDataFunctions){
        if (data[k] === undefined) {
            clipboardData.setData(k, '');
        }
    }
    for(const k in data){
        const v = data[k];
        if (v !== undefined) {
            clipboardData.setData(k, v);
        }
    }
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/dragon/LexicalDragon.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DragonExtension",
    ()=>DragonExtension,
    "registerDragonSupport",
    ()=>registerDragonSupport
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/extension/LexicalExtension.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function registerDragonSupport(editor) {
    const origin = window.location.origin;
    const handler = (event)=>{
        if (event.origin !== origin) {
            return;
        }
        const rootElement = editor.getRootElement();
        if (document.activeElement !== rootElement) {
            return;
        }
        const data = event.data;
        if (typeof data === 'string') {
            let parsedData;
            try {
                parsedData = JSON.parse(data);
            } catch (_e) {
                return;
            }
            if (parsedData && parsedData.protocol === 'nuanria_messaging' && parsedData.type === 'request') {
                const payload = parsedData.payload;
                if (payload && payload.functionId === 'makeChanges') {
                    const args = payload.args;
                    if (args) {
                        const [elementStart, elementLength, text, selStart, selLength] = args;
                        // TODO: we should probably handle formatCommand somehow?
                        // formatCommand;
                        editor.update(()=>{
                            const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
                            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
                                const anchor = selection.anchor;
                                let anchorNode = anchor.getNode();
                                let setSelStart = 0;
                                let setSelEnd = 0;
                                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(anchorNode)) {
                                    // set initial selection
                                    if (elementStart >= 0 && elementLength >= 0) {
                                        setSelStart = elementStart;
                                        setSelEnd = elementStart + elementLength;
                                        // If the offset is more than the end, make it the end
                                        selection.setTextNodeRange(anchorNode, setSelStart, anchorNode, setSelEnd);
                                    }
                                }
                                if (setSelStart !== setSelEnd || text !== '') {
                                    selection.insertRawText(text);
                                    anchorNode = anchor.getNode();
                                }
                                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(anchorNode)) {
                                    // set final selection
                                    setSelStart = selStart;
                                    setSelEnd = selStart + selLength;
                                    const anchorNodeTextLength = anchorNode.getTextContentSize();
                                    // If the offset is more than the end, make it the end
                                    setSelStart = setSelStart > anchorNodeTextLength ? anchorNodeTextLength : setSelStart;
                                    setSelEnd = setSelEnd > anchorNodeTextLength ? anchorNodeTextLength : setSelEnd;
                                    selection.setTextNodeRange(anchorNode, setSelStart, anchorNode, setSelEnd);
                                }
                                // block the chrome extension from handling this event
                                event.stopImmediatePropagation();
                            }
                        });
                    }
                }
            }
        }
    };
    window.addEventListener('message', handler, true);
    return ()=>{
        window.removeEventListener('message', handler, true);
    };
}
/**
 * Add Dragon speech to text input support to the editor, via the
 * \@lexical/dragon module.
 */ const DragonExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build: (editor, config, state)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["namedSignals"])(config),
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        disabled: ("TURBOPACK compile-time value", "undefined") === 'undefined'
    }),
    name: '@lexical/dragon',
    register: (editor, config, state)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["effect"])(()=>state.getOutput().disabled.value ? undefined : registerDragonSupport(editor))
});
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/extension/LexicalExtension.dev.mjs [app-rsc] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$createHorizontalRuleNode",
    ()=>$createHorizontalRuleNode,
    "$isDecoratorTextNode",
    ()=>$isDecoratorTextNode,
    "$isHorizontalRuleNode",
    ()=>$isHorizontalRuleNode,
    "AutoFocusExtension",
    ()=>AutoFocusExtension,
    "ClearEditorExtension",
    ()=>ClearEditorExtension,
    "DecoratorTextExtension",
    ()=>DecoratorTextExtension,
    "DecoratorTextNode",
    ()=>DecoratorTextNode,
    "EditorStateExtension",
    ()=>EditorStateExtension,
    "HorizontalRuleExtension",
    ()=>HorizontalRuleExtension,
    "HorizontalRuleNode",
    ()=>HorizontalRuleNode,
    "INSERT_HORIZONTAL_RULE_COMMAND",
    ()=>INSERT_HORIZONTAL_RULE_COMMAND,
    "InitialStateExtension",
    ()=>InitialStateExtension,
    "LexicalBuilder",
    ()=>LexicalBuilder,
    "NodeSelectionExtension",
    ()=>NodeSelectionExtension,
    "TabIndentationExtension",
    ()=>TabIndentationExtension,
    "applyFormatFromStyle",
    ()=>applyFormatFromStyle,
    "applyFormatToDom",
    ()=>applyFormatToDom,
    "batch",
    ()=>o,
    "buildEditorFromExtensions",
    ()=>buildEditorFromExtensions,
    "computed",
    ()=>w,
    "effect",
    ()=>E,
    "getExtensionDependencyFromEditor",
    ()=>getExtensionDependencyFromEditor,
    "getKnownTypesAndNodes",
    ()=>getKnownTypesAndNodes,
    "getPeerDependencyFromEditor",
    ()=>getPeerDependencyFromEditor,
    "getPeerDependencyFromEditorOrThrow",
    ()=>getPeerDependencyFromEditorOrThrow,
    "namedSignals",
    ()=>namedSignals,
    "registerClearEditor",
    ()=>registerClearEditor,
    "registerTabIndentation",
    ()=>registerTabIndentation,
    "signal",
    ()=>d,
    "untracked",
    ()=>h,
    "watchedSignal",
    ()=>watchedSignal
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/utils/LexicalUtils.dev.mjs [app-rsc] (ecmascript) <locals>");
;
;
;
const i = Symbol.for("preact-signals");
function t() {
    if (r > 1) {
        r--;
        return;
    }
    let i, t = false;
    while(void 0 !== s){
        let o = s;
        s = void 0;
        f++;
        while(void 0 !== o){
            const n = o.o;
            o.o = void 0;
            o.f &= -3;
            if (!(8 & o.f) && v(o)) try {
                o.c();
            } catch (o) {
                if (!t) {
                    i = o;
                    t = true;
                }
            }
            o = n;
        }
    }
    f = 0;
    r--;
    if (t) throw i;
}
function o(i) {
    if (r > 0) return i();
    r++;
    try {
        return i();
    } finally{
        t();
    }
}
let n, s;
function h(i) {
    const t = n;
    n = void 0;
    try {
        return i();
    } finally{
        n = t;
    }
}
let r = 0, f = 0, e = 0;
function u(i) {
    if (void 0 === n) return;
    let t = i.n;
    if (void 0 === t || t.t !== n) {
        t = {
            i: 0,
            S: i,
            p: n.s,
            n: void 0,
            t: n,
            e: void 0,
            x: void 0,
            r: t
        };
        if (void 0 !== n.s) n.s.n = t;
        n.s = t;
        i.n = t;
        if (32 & n.f) i.S(t);
        return t;
    } else if (-1 === t.i) {
        t.i = 0;
        if (void 0 !== t.n) {
            t.n.p = t.p;
            if (void 0 !== t.p) t.p.n = t.n;
            t.p = n.s;
            t.n = void 0;
            n.s.n = t;
            n.s = t;
        }
        return t;
    }
}
function c(i, t) {
    this.v = i;
    this.i = 0;
    this.n = void 0;
    this.t = void 0;
    this.W = null == t ? void 0 : t.watched;
    this.Z = null == t ? void 0 : t.unwatched;
    this.name = null == t ? void 0 : t.name;
}
c.prototype.brand = i;
c.prototype.h = function() {
    return true;
};
c.prototype.S = function(i) {
    const t = this.t;
    if (t !== i && void 0 === i.e) {
        i.x = t;
        this.t = i;
        if (void 0 !== t) t.e = i;
        else h(()=>{
            var i;
            null == (i = this.W) || i.call(this);
        });
    }
};
c.prototype.U = function(i) {
    if (void 0 !== this.t) {
        const t = i.e, o = i.x;
        if (void 0 !== t) {
            t.x = o;
            i.e = void 0;
        }
        if (void 0 !== o) {
            o.e = t;
            i.x = void 0;
        }
        if (i === this.t) {
            this.t = o;
            if (void 0 === o) h(()=>{
                var i;
                null == (i = this.Z) || i.call(this);
            });
        }
    }
};
c.prototype.subscribe = function(i) {
    return E(()=>{
        const t = this.value, o = n;
        n = void 0;
        try {
            i(t);
        } finally{
            n = o;
        }
    }, {
        name: "sub"
    });
};
c.prototype.valueOf = function() {
    return this.value;
};
c.prototype.toString = function() {
    return this.value + "";
};
c.prototype.toJSON = function() {
    return this.value;
};
c.prototype.peek = function() {
    const i = n;
    n = void 0;
    try {
        return this.value;
    } finally{
        n = i;
    }
};
Object.defineProperty(c.prototype, "value", {
    get () {
        const i = u(this);
        if (void 0 !== i) i.i = this.i;
        return this.v;
    },
    set (i) {
        if (i !== this.v) {
            if (f > 100) throw new Error("Cycle detected");
            this.v = i;
            this.i++;
            e++;
            r++;
            try {
                for(let i = this.t; void 0 !== i; i = i.x)i.t.N();
            } finally{
                t();
            }
        }
    }
});
function d(i, t) {
    return new c(i, t);
}
function v(i) {
    for(let t = i.s; void 0 !== t; t = t.n)if (t.S.i !== t.i || !t.S.h() || t.S.i !== t.i) return true;
    return false;
}
function l(i) {
    for(let t = i.s; void 0 !== t; t = t.n){
        const o = t.S.n;
        if (void 0 !== o) t.r = o;
        t.S.n = t;
        t.i = -1;
        if (void 0 === t.n) {
            i.s = t;
            break;
        }
    }
}
function y(i) {
    let t, o = i.s;
    while(void 0 !== o){
        const i = o.p;
        if (-1 === o.i) {
            o.S.U(o);
            if (void 0 !== i) i.n = o.n;
            if (void 0 !== o.n) o.n.p = i;
        } else t = o;
        o.S.n = o.r;
        if (void 0 !== o.r) o.r = void 0;
        o = i;
    }
    i.s = t;
}
function a(i, t) {
    c.call(this, void 0);
    this.x = i;
    this.s = void 0;
    this.g = e - 1;
    this.f = 4;
    this.W = null == t ? void 0 : t.watched;
    this.Z = null == t ? void 0 : t.unwatched;
    this.name = null == t ? void 0 : t.name;
}
a.prototype = new c;
a.prototype.h = function() {
    this.f &= -3;
    if (1 & this.f) return false;
    if (32 == (36 & this.f)) return true;
    this.f &= -5;
    if (this.g === e) return true;
    this.g = e;
    this.f |= 1;
    if (this.i > 0 && !v(this)) {
        this.f &= -2;
        return true;
    }
    const i = n;
    try {
        l(this);
        n = this;
        const i = this.x();
        if (16 & this.f || this.v !== i || 0 === this.i) {
            this.v = i;
            this.f &= -17;
            this.i++;
        }
    } catch (i) {
        this.v = i;
        this.f |= 16;
        this.i++;
    }
    n = i;
    y(this);
    this.f &= -2;
    return true;
};
a.prototype.S = function(i) {
    if (void 0 === this.t) {
        this.f |= 36;
        for(let i = this.s; void 0 !== i; i = i.n)i.S.S(i);
    }
    c.prototype.S.call(this, i);
};
a.prototype.U = function(i) {
    if (void 0 !== this.t) {
        c.prototype.U.call(this, i);
        if (void 0 === this.t) {
            this.f &= -33;
            for(let i = this.s; void 0 !== i; i = i.n)i.S.U(i);
        }
    }
};
a.prototype.N = function() {
    if (!(2 & this.f)) {
        this.f |= 6;
        for(let i = this.t; void 0 !== i; i = i.x)i.t.N();
    }
};
Object.defineProperty(a.prototype, "value", {
    get () {
        if (1 & this.f) throw new Error("Cycle detected");
        const i = u(this);
        this.h();
        if (void 0 !== i) i.i = this.i;
        if (16 & this.f) throw this.v;
        return this.v;
    }
});
function w(i, t) {
    return new a(i, t);
}
function _(i) {
    const o = i.u;
    i.u = void 0;
    if ("function" == typeof o) {
        r++;
        const s = n;
        n = void 0;
        try {
            o();
        } catch (t) {
            i.f &= -2;
            i.f |= 8;
            b(i);
            throw t;
        } finally{
            n = s;
            t();
        }
    }
}
function b(i) {
    for(let t = i.s; void 0 !== t; t = t.n)t.S.U(t);
    i.x = void 0;
    i.s = void 0;
    _(i);
}
function g(i) {
    if (n !== this) throw new Error("Out-of-order effect");
    y(this);
    n = i;
    this.f &= -2;
    if (8 & this.f) b(this);
    t();
}
function p(i, t) {
    this.x = i;
    this.u = void 0;
    this.s = void 0;
    this.o = void 0;
    this.f = 32;
    this.name = null == t ? void 0 : t.name;
}
p.prototype.c = function() {
    const i = this.S();
    try {
        if (8 & this.f) return;
        if (void 0 === this.x) return;
        const t = this.x();
        if ("function" == typeof t) this.u = t;
    } finally{
        i();
    }
};
p.prototype.S = function() {
    if (1 & this.f) throw new Error("Cycle detected");
    this.f |= 1;
    this.f &= -9;
    _(this);
    l(this);
    r++;
    const i = n;
    n = this;
    return g.bind(this, i);
};
p.prototype.N = function() {
    if (!(2 & this.f)) {
        this.f |= 2;
        this.o = s;
        s = this;
    }
};
p.prototype.d = function() {
    this.f |= 8;
    if (!(1 & this.f)) b(this);
};
p.prototype.dispose = function() {
    this.d();
};
function E(i, t) {
    const o = new p(i, t);
    try {
        o.c();
    } catch (i) {
        o.d();
        throw i;
    }
    const n = o.d.bind(o);
    n[Symbol.dispose] = n;
    return n;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * @experimental
 * Return an object with the same shape as `defaults` with a {@link Signal}
 * for each value. If specified, the second `opts` argument is a partial
 * of overrides to the defaults and will be used as the initial value.
 *
 * Typically used to make a reactive version of some subset of the
 * configuration of an extension, so it can be reconfigured at runtime.
 *
 * @param defaults The object with default values
 * @param opts Overrides to those default values
 * @returns An object with signals initialized with the default values
 */ function namedSignals(defaults, opts = {}) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const initial = {};
    for(const k in defaults){
        const v = opts[k];
        const store = d(v === undefined ? defaults[k] : v);
        initial[k] = store;
    }
    return initial;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * An Extension to focus the LexicalEditor when the root element is set
 * (typically only when the editor is first created).
 */ const AutoFocusExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build: (editor, config, state)=>{
        return namedSignals(config);
    },
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        defaultSelection: 'rootEnd',
        disabled: false
    }),
    name: '@lexical/extension/AutoFocus',
    register (editor, config, state) {
        const stores = state.getOutput();
        return E(()=>stores.disabled.value ? undefined : editor.registerRootListener((rootElement)=>{
                editor.focus(()=>{
                    // If we try and move selection to the same point with setBaseAndExtent, it won't
                    // trigger a re-focus on the element. So in the case this occurs, we'll need to correct it.
                    // Normally this is fine, Selection API !== Focus API, but fore the intents of the naming
                    // of this plugin, which should preserve focus too.
                    const activeElement = document.activeElement;
                    if (rootElement !== null && (activeElement === null || !rootElement.contains(activeElement))) {
                        // Note: preventScroll won't work in Webkit.
                        rootElement.focus({
                            preventScroll: true
                        });
                    }
                }, {
                    defaultSelection: stores.defaultSelection.peek()
                });
            }));
    }
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function $defaultOnClear() {
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])();
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
    root.clear();
    root.append(paragraph);
    if (selection !== null) {
        paragraph.select();
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        selection.format = 0;
    }
}
function registerClearEditor(editor, $onClear = $defaultOnClear) {
    return editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CLEAR_EDITOR_COMMAND"], (payload)=>{
        editor.update($onClear);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]);
}
/**
 * An extension to provide an implementation of {@link CLEAR_EDITOR_COMMAND}
 */ const ClearEditorExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build (editor, config, state) {
        return namedSignals(config);
    },
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        $onClear: $defaultOnClear
    }),
    name: '@lexical/extension/ClearEditor',
    register (editor, config, state) {
        const { $onClear } = state.getOutput();
        return E(()=>registerClearEditor(editor, $onClear.value));
    }
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * @experimental
 * Get the sets of nodes and types registered in the
 * {@link InitialEditorConfig}. This is to be used when an extension
 * needs to register optional behavior if some node or type is present.
 *
 * @param config The InitialEditorConfig (accessible from an extension's init)
 * @returns The known types and nodes as Sets
 */ function getKnownTypesAndNodes(config) {
    const types = new Set();
    const nodes = new Set();
    for (const klassOrReplacement of getNodeConfig(config)){
        const klass = typeof klassOrReplacement === 'function' ? klassOrReplacement : klassOrReplacement.replace;
        types.add(klass.getType());
        nodes.add(klass);
    }
    return {
        nodes,
        types
    };
}
function getNodeConfig(config) {
    return (typeof config.nodes === 'function' ? config.nodes() : config.nodes) || [];
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const formatState = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createState"])('format', {
    parse: (value)=>typeof value === 'number' ? value : 0
});
class DecoratorTextNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DecoratorNode"] {
    $config() {
        return this.config('decorator-text', {
            extends: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DecoratorNode"],
            stateConfigs: [
                {
                    flat: true,
                    stateConfig: formatState
                }
            ]
        });
    }
    getFormat() {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getState"])(this, formatState);
    }
    getFormatFlags(type, alignWithFormat) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["toggleTextFormatType"])(this.getFormat(), type, alignWithFormat);
    }
    hasFormat(type) {
        const formatFlag = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TEXT_TYPE_TO_FORMAT"][type];
        return (this.getFormat() & formatFlag) !== 0;
    }
    setFormat(type) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setState"])(this, formatState, type);
    }
    toggleFormat(type) {
        const format = this.getFormat();
        const newFormat = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["toggleTextFormatType"])(format, type, null);
        return this.setFormat(newFormat);
    }
    isInline() {
        return true;
    }
    createDOM() {
        return document.createElement('span');
    }
    updateDOM() {
        return false;
    }
}
function $isDecoratorTextNode(node) {
    return node instanceof DecoratorTextNode;
}
/**
 * Applies formatting to the node based on the properties in the passed style object.
 * By default, properties are checked according to the values set
 * when importing content from Google Docs.
 * This algorithm is identical to the TextNode import.

 * @param lexicalNode The node to which the format will apply
 * @param style CSS style object
 * @param shouldApply format to apply if it is not in style
 * @returns lexicalNode
 */ function applyFormatFromStyle(lexicalNode, style, shouldApply) {
    const fontWeight = style.fontWeight;
    const textDecoration = style.textDecoration.split(' ');
    // Google Docs uses span tags + font-weight for bold text
    const hasBoldFontWeight = fontWeight === '700' || fontWeight === 'bold';
    // Google Docs uses span tags + text-decoration: line-through for strikethrough text
    const hasLinethroughTextDecoration = textDecoration.includes('line-through');
    // Google Docs uses span tags + font-style for italic text
    const hasItalicFontStyle = style.fontStyle === 'italic';
    // Google Docs uses span tags + text-decoration: underline for underline text
    const hasUnderlineTextDecoration = textDecoration.includes('underline');
    // Google Docs uses span tags + vertical-align to specify subscript and superscript
    const verticalAlign = style.verticalAlign;
    if (hasBoldFontWeight && !lexicalNode.hasFormat('bold')) {
        lexicalNode.toggleFormat('bold');
    }
    if (hasLinethroughTextDecoration && !lexicalNode.hasFormat('strikethrough')) {
        lexicalNode.toggleFormat('strikethrough');
    }
    if (hasItalicFontStyle && !lexicalNode.hasFormat('italic')) {
        lexicalNode.toggleFormat('italic');
    }
    if (hasUnderlineTextDecoration && !lexicalNode.hasFormat('underline')) {
        lexicalNode.toggleFormat('underline');
    }
    if (verticalAlign === 'sub' && !lexicalNode.hasFormat('subscript')) {
        lexicalNode.toggleFormat('subscript');
    }
    if (verticalAlign === 'super' && !lexicalNode.hasFormat('superscript')) {
        lexicalNode.toggleFormat('superscript');
    }
    if (shouldApply && !lexicalNode.hasFormat(shouldApply)) {
        lexicalNode.toggleFormat(shouldApply);
    }
    return lexicalNode;
}
/**
 * The function wraps the passed DOM node in semantic tags depending on the node format.
 *
 * @param lexicalNode The node where the format is checked
 * @param domNode DOM that will be wrapped in tags
 * @param tagNameToFormat Tag name and format mapping
 * @returns domNode
 */ function applyFormatToDom(lexicalNode, domNode, tagNameToFormat = DEFAULT_TAG_NAME_TO_FORMAT) {
    for (const [tag, format] of Object.entries(tagNameToFormat)){
        if (lexicalNode.hasFormat(format)) {
            domNode = wrapElementWith(domNode, tag);
        }
    }
    return domNode;
}
function wrapElementWith(element, tag) {
    const el = document.createElement(tag);
    el.appendChild(element);
    return el;
}
const DEFAULT_TAG_NAME_TO_FORMAT = {
    b: 'bold',
    code: 'code',
    em: 'italic',
    i: 'italic',
    mark: 'highlight',
    s: 'strikethrough',
    strong: 'bold',
    sub: 'subscript',
    sup: 'superscript',
    u: 'underline'
};
/**
 * An extension for DecoratorTextNode that sets the format for the node and CSS classes for the DOM container.
 * The base class is always set, and the focus class is set when the node is selected.
 */ const DecoratorTextExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    name: '@lexical/extension/DecoratorText',
    nodes: ()=>[
            DecoratorTextNode
        ],
    register (editor, config, state) {
        return editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["FORMAT_TEXT_COMMAND"], (formatType)=>{
            const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
                for (const node of selection.getNodes()){
                    if ($isDecoratorTextNode(node)) {
                        node.toggleFormat(formatType);
                    }
                }
            }
            return false;
        }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]);
    }
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * @experimental
 * Create a Signal that will subscribe to a value from an external store when watched, similar to
 * React's [useSyncExternalStore](https://react.dev/reference/react/useSyncExternalStore).
 *
 * @param getSnapshot Used to get the initial value of the signal when created and when first watched.
 * @param register A callback that will subscribe to some external store and update the signal, must return a dispose function.
 * @returns The signal
 */ function watchedSignal(getSnapshot, register) {
    let dispose;
    return d(getSnapshot(), {
        unwatched () {
            if (dispose) {
                dispose();
                dispose = undefined;
            }
        },
        watched () {
            this.value = getSnapshot();
            dispose = register(this);
        }
    });
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * An extension to provide the current EditorState as a signal
 */ const EditorStateExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build (editor) {
        return watchedSignal(()=>editor.getEditorState(), (editorStateSignal)=>editor.registerUpdateListener((payload)=>{
                editorStateSignal.value = payload.editorState;
            }));
    },
    name: '@lexical/extension/EditorState'
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ // Do not require this module directly! Use normal `invariant` calls.
function formatDevErrorMessage(message) {
    throw new Error(message);
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * Recursively merge the given theme configuration in-place.
 *
 * @returns If `a` and `b` are both objects (and `b` is not an Array) then
 * all keys in `b` are merged into `a` then `a` is returned.
 * Otherwise `b` is returned.
 *
 * @example
 * ```ts
 * const a = { a: "a", nested: { a: 1 } };
 * const b = { b: "b", nested: { b: 2 } };
 * const rval = deepThemeMergeInPlace(a, b);
 * expect(a).toBe(rval);
 * expect(a).toEqual({ a: "a", b: "b", nested: { a: 1, b: 2 } });
 * ```
 */ function deepThemeMergeInPlace(a, b) {
    if (a && b && !Array.isArray(b) && typeof a === 'object' && typeof b === 'object') {
        const aObj = a;
        const bObj = b;
        for(const k in bObj){
            aObj[k] = deepThemeMergeInPlace(aObj[k], bObj[k]);
        }
        return a;
    }
    return b;
}
const ExtensionRepStateIds = {
    /* eslint-disable sort-keys-fix/sort-keys-fix */ unmarked: 0,
    temporary: 1,
    permanent: 2,
    configured: 3,
    initialized: 4,
    built: 5,
    registered: 6,
    afterRegistration: 7
};
function isExactlyUnmarkedExtensionRepState(state) {
    return state.id === ExtensionRepStateIds.unmarked;
}
function isExactlyTemporaryExtensionRepState(state) {
    return state.id === ExtensionRepStateIds.temporary;
}
function isExactlyPermanentExtensionRepState(state) {
    return state.id === ExtensionRepStateIds.permanent;
}
function isConfiguredExtensionRepState(state) {
    return state.id >= ExtensionRepStateIds.configured;
}
function isInitializedExtensionRepState(state) {
    return state.id >= ExtensionRepStateIds.initialized;
}
function isBuiltExtensionRepState(state) {
    return state.id >= ExtensionRepStateIds.built;
}
function isAfterRegistrationState(state) {
    return state.id >= ExtensionRepStateIds.afterRegistration;
}
function applyTemporaryMark(state) {
    if (!isExactlyUnmarkedExtensionRepState(state)) {
        formatDevErrorMessage(`LexicalBuilder: Can not apply a temporary mark from state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.unmarked)} unmarked)`);
    }
    return Object.assign(state, {
        id: ExtensionRepStateIds.temporary
    });
}
function applyPermanentMark(state) {
    if (!isExactlyTemporaryExtensionRepState(state)) {
        formatDevErrorMessage(`LexicalBuilder: Can not apply a permanent mark from state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.temporary)} temporary)`);
    }
    return Object.assign(state, {
        id: ExtensionRepStateIds.permanent
    });
}
function applyConfiguredState(state, config, registerState) {
    return Object.assign(state, {
        config,
        id: ExtensionRepStateIds.configured,
        registerState
    });
}
function applyInitializedState(state, initResult, registerState) {
    return Object.assign(state, {
        id: ExtensionRepStateIds.initialized,
        initResult,
        registerState
    });
}
function applyBuiltState(state, output, registerState) {
    return Object.assign(state, {
        id: ExtensionRepStateIds.built,
        output,
        registerState
    });
}
function applyRegisteredState(state) {
    return Object.assign(state, {
        id: ExtensionRepStateIds.registered
    });
}
function applyAfterRegistrationState(state) {
    return Object.assign(state, {
        id: ExtensionRepStateIds.afterRegistration
    });
}
function rollbackToBuiltState(state) {
    return Object.assign(state, {
        id: ExtensionRepStateIds.built
    });
}
const emptySet = new Set();
/**
 * @internal
 */ class ExtensionRep {
    builder;
    configs;
    _dependency;
    _peerNameSet;
    extension;
    state;
    _signal;
    constructor(builder, extension){
        this.builder = builder;
        this.extension = extension;
        this.configs = new Set();
        this.state = {
            id: ExtensionRepStateIds.unmarked
        };
    }
    mergeConfigs() {
        // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- LexicalExtensionConfig<Extension> is any
        let config = this.extension.config || {};
        const mergeConfig = this.extension.mergeConfig ? this.extension.mergeConfig.bind(this.extension) : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["shallowMergeConfig"];
        for (const cfg of this.configs){
            // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment -- LexicalExtensionConfig<Extension> is any
            config = mergeConfig(config, cfg);
        }
        // eslint-disable-next-line @typescript-eslint/no-unsafe-return -- any
        return config;
    }
    init(editorConfig) {
        const initialState = this.state;
        if (!isExactlyPermanentExtensionRepState(initialState)) {
            formatDevErrorMessage(`ExtensionRep: Can not configure from state id ${String(initialState.id)}`);
        }
        const initState = {
            getDependency: this.getInitDependency.bind(this),
            getDirectDependentNames: this.getDirectDependentNames.bind(this),
            getPeer: this.getInitPeer.bind(this),
            getPeerNameSet: this.getPeerNameSet.bind(this)
        };
        const buildState = {
            ...initState,
            getDependency: this.getDependency.bind(this),
            getInitResult: this.getInitResult.bind(this),
            getPeer: this.getPeer.bind(this)
        };
        const state = applyConfiguredState(initialState, this.mergeConfigs(), initState);
        this.state = state;
        let initResult;
        if (this.extension.init) {
            initResult = this.extension.init(editorConfig, state.config, initState);
        }
        // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion -- false positive
        this.state = applyInitializedState(state, initResult, buildState);
    }
    build(editor) {
        const state = this.state;
        if (!(state.id === ExtensionRepStateIds.initialized)) {
            formatDevErrorMessage(`ExtensionRep: register called in state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.built)} initialized)`);
        }
        let output;
        if (this.extension.build) {
            output = this.extension.build(editor, state.config, state.registerState);
        }
        const registerState = {
            ...state.registerState,
            getOutput: ()=>output,
            getSignal: this.getSignal.bind(this)
        };
        this.state = applyBuiltState(state, output, registerState);
    }
    register(editor, signal) {
        this._signal = signal;
        const state = this.state;
        if (!(state.id === ExtensionRepStateIds.built)) {
            formatDevErrorMessage(`ExtensionRep: register called in state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.built)} built)`);
        }
        const cleanup = this.extension.register && this.extension.register(editor, state.config, state.registerState);
        this.state = applyRegisteredState(state);
        return ()=>{
            const afterRegistrationState = this.state;
            if (!(afterRegistrationState.id === ExtensionRepStateIds.afterRegistration)) {
                formatDevErrorMessage(`ExtensionRep: rollbackToBuiltState called in state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.afterRegistration)} afterRegistration)`);
            }
            this.state = rollbackToBuiltState(afterRegistrationState);
            if (cleanup) {
                cleanup();
            }
        };
    }
    afterRegistration(editor) {
        const state = this.state;
        if (!(state.id === ExtensionRepStateIds.registered)) {
            formatDevErrorMessage(`ExtensionRep: afterRegistration called in state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.registered)} registered)`);
        }
        let rval;
        if (this.extension.afterRegistration) {
            rval = this.extension.afterRegistration(editor, state.config, state.registerState);
        }
        this.state = applyAfterRegistrationState(state);
        return rval;
    }
    getSignal() {
        if (!(this._signal !== undefined)) {
            formatDevErrorMessage(`ExtensionRep.getSignal() called before register`);
        }
        return this._signal;
    }
    getInitResult() {
        if (!(this.extension.init !== undefined)) {
            formatDevErrorMessage(`ExtensionRep: getInitResult() called for Extension ${this.extension.name} that does not define init`);
        }
        const state = this.state;
        if (!isInitializedExtensionRepState(state)) {
            formatDevErrorMessage(`ExtensionRep: getInitResult() called for ExtensionRep in state id ${String(state.id)} < ${String(ExtensionRepStateIds.initialized)} (initialized)`);
        } // eslint-disable-next-line @typescript-eslint/no-unsafe-return -- any
        return state.initResult;
    }
    getInitPeer(name) {
        const rep = this.builder.extensionNameMap.get(name);
        return rep ? rep.getExtensionInitDependency() : undefined;
    }
    getExtensionInitDependency() {
        const state = this.state;
        if (!isConfiguredExtensionRepState(state)) {
            formatDevErrorMessage(`ExtensionRep: getExtensionInitDependency called in state id ${String(state.id)} (expected >= ${String(ExtensionRepStateIds.configured)} configured)`);
        }
        return {
            config: state.config
        };
    }
    getPeer(name) {
        const rep = this.builder.extensionNameMap.get(name);
        return rep ? rep.getExtensionDependency() : undefined;
    }
    getInitDependency(dep) {
        const rep = this.builder.getExtensionRep(dep);
        if (!(rep !== undefined)) {
            formatDevErrorMessage(`LexicalExtensionBuilder: Extension ${this.extension.name} missing dependency extension ${dep.name} to be in registry`);
        }
        return rep.getExtensionInitDependency();
    }
    getDependency(dep) {
        const rep = this.builder.getExtensionRep(dep);
        if (!(rep !== undefined)) {
            formatDevErrorMessage(`LexicalExtensionBuilder: Extension ${this.extension.name} missing dependency extension ${dep.name} to be in registry`);
        }
        return rep.getExtensionDependency();
    }
    getState() {
        const state = this.state;
        if (!isAfterRegistrationState(state)) {
            formatDevErrorMessage(`ExtensionRep getState called in state id ${String(state.id)} (expected ${String(ExtensionRepStateIds.afterRegistration)} afterRegistration)`);
        }
        return state;
    }
    getDirectDependentNames() {
        return this.builder.incomingEdges.get(this.extension.name) || emptySet;
    }
    getPeerNameSet() {
        let s = this._peerNameSet;
        if (!s) {
            s = new Set((this.extension.peerDependencies || []).map(([name])=>name));
            this._peerNameSet = s;
        }
        return s;
    }
    getExtensionDependency() {
        if (!this._dependency) {
            const state = this.state;
            if (!isBuiltExtensionRepState(state)) {
                formatDevErrorMessage(`Extension ${this.extension.name} used as a dependency before build`);
            }
            this._dependency = {
                config: state.config,
                init: state.initResult,
                output: state.output
            };
        }
        return this._dependency;
    }
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const HISTORY_MERGE_OPTIONS = {
    tag: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["HISTORY_MERGE_TAG"]
};
function $defaultInitializer() {
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])();
    if (root.isEmpty()) {
        root.append((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])());
    }
}
/**
 * An extension to set the initial state of the editor from
 * a function or serialized JSON EditorState. This is
 * implicitly included with all editors built with
 * Lexical Extension. This happens in the `afterRegistration`
 * phase so your initial state may depend on registered commands,
 * but you should not call `editor.setRootElement` earlier than
 * this phase to avoid rendering an empty editor first.
 */ const InitialStateExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        setOptions: HISTORY_MERGE_OPTIONS,
        updateOptions: HISTORY_MERGE_OPTIONS
    }),
    init ({ $initialEditorState = $defaultInitializer }) {
        return {
            $initialEditorState,
            initialized: false
        };
    },
    // eslint-disable-next-line sort-keys-fix/sort-keys-fix -- typescript inference is order dependent here for some reason
    afterRegistration (editor, { updateOptions, setOptions }, state) {
        const initResult = state.getInitResult();
        if (!initResult.initialized) {
            initResult.initialized = true;
            const { $initialEditorState } = initResult;
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isEditorState"])($initialEditorState)) {
                editor.setEditorState($initialEditorState, setOptions);
            } else if (typeof $initialEditorState === 'function') {
                editor.update(()=>{
                    $initialEditorState(editor);
                }, updateOptions);
            } else if ($initialEditorState && (typeof $initialEditorState === 'string' || typeof $initialEditorState === 'object')) {
                const parsedEditorState = editor.parseEditorState($initialEditorState);
                editor.setEditorState(parsedEditorState, setOptions);
            }
        }
        return ()=>{};
    },
    name: '@lexical/extension/InitialState',
    // These are automatically added by createEditor, we add them here so they are
    // visible during extensionRep.init so extensions can see all known types before the
    // editor is created.
    // (excluding ArtificialNode__DO_NOT_USE because it isn't really public API
    // and shouldn't change anything)
    nodes: [
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["RootNode"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TextNode"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["LineBreakNode"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TabNode"],
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ParagraphNode"]
    ]
});
/** @internal Use a well-known symbol for dev tools purposes */ const builderSymbol = Symbol.for('@lexical/extension/LexicalBuilder');
/**
 * Build a LexicalEditor by combining together one or more extensions, optionally
 * overriding some of their configuration.
 *
 * @param extensions - Extension arguments (extensions or extensions with config overrides)
 * @returns An editor handle
 *
 * @example
 * A single root extension with multiple dependencies
 *
 * ```ts
 * const editor = buildEditorFromExtensions(
 *   defineExtension({
 *     name: "[root]",
 *     dependencies: [
 *       RichTextExtension,
 *       configExtension(EmojiExtension, { emojiBaseUrl: "/assets/emoji" }),
 *     ],
 *     register: (editor: LexicalEditor) => {
 *       console.log("Editor Created");
 *       return () => console.log("Editor Disposed");
 *     },
 *   }),
 * );
 * ```
 *
 * @example
 * A very similar minimal configuration without the register hook
 *
 * ```ts
 * const editor = buildEditorFromExtensions(
 *   RichTextExtension,
 *   configExtension(EmojiExtension, { emojiBaseUrl: "/assets/emoji" }),
 * );
 * ```
 */ function buildEditorFromExtensions(...extensions) {
    return LexicalBuilder.fromExtensions(extensions).buildEditor();
}
/** @internal */ function noop() {
/*empty*/ }
/** Throw the given Error */ function defaultOnError(err) {
    throw err;
}
/** @internal */ function maybeWithBuilder(editor) {
    return editor;
}
function normalizeExtensionArgument(arg) {
    return Array.isArray(arg) ? arg : [
        arg
    ];
}
const PACKAGE_VERSION = "0.41.0+dev.esm";
/** @internal */ class LexicalBuilder {
    roots;
    extensionNameMap;
    outgoingConfigEdges;
    incomingEdges;
    conflicts;
    _sortedExtensionReps;
    PACKAGE_VERSION;
    constructor(roots){
        this.outgoingConfigEdges = new Map();
        this.incomingEdges = new Map();
        this.extensionNameMap = new Map();
        this.conflicts = new Map();
        this.PACKAGE_VERSION = PACKAGE_VERSION;
        this.roots = roots;
        for (const extension of roots){
            this.addExtension(extension);
        }
    }
    static fromExtensions(extensions) {
        const roots = [
            normalizeExtensionArgument(InitialStateExtension)
        ];
        for (const extension of extensions){
            roots.push(normalizeExtensionArgument(extension));
        }
        return new LexicalBuilder(roots);
    }
    static maybeFromEditor(editor) {
        const builder = maybeWithBuilder(editor)[builderSymbol];
        if (builder) {
            // The dev tools variant of this will relax some of these invariants
            if (!(builder.PACKAGE_VERSION === PACKAGE_VERSION)) {
                formatDevErrorMessage(`LexicalBuilder.fromEditor: The given editor was created with LexicalBuilder ${builder.PACKAGE_VERSION} but this version is ${PACKAGE_VERSION}. A project should have exactly one copy of LexicalBuilder`);
            }
            if (!(builder instanceof LexicalBuilder)) {
                formatDevErrorMessage(`LexicalBuilder.fromEditor: There are multiple copies of the same version of LexicalBuilder in your project, and this editor was created with another one. Your project, or one of its dependencies, has its package.json and/or bundler configured incorrectly.`);
            }
        }
        return builder;
    }
    /** Look up the editor that was created by this LexicalBuilder or throw */ static fromEditor(editor) {
        const builder = LexicalBuilder.maybeFromEditor(editor);
        if (!(builder !== undefined)) {
            formatDevErrorMessage(`LexicalBuilder.fromEditor: The given editor was not created with LexicalBuilder`);
        }
        return builder;
    }
    constructEditor() {
        const { $initialEditorState: _$initialEditorState, onError, ...editorConfig } = this.buildCreateEditorArgs();
        const editor = Object.assign((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createEditor"])({
            ...editorConfig,
            ...onError ? {
                onError: (err)=>{
                    onError(err, editor);
                }
            } : {}
        }), {
            [builderSymbol]: this
        });
        for (const extensionRep of this.sortedExtensionReps()){
            extensionRep.build(editor);
        }
        return editor;
    }
    buildEditor() {
        let disposeOnce = noop;
        function dispose() {
            try {
                disposeOnce();
            } finally{
                disposeOnce = noop;
            }
        }
        const editor = Object.assign(this.constructEditor(), {
            dispose,
            [Symbol.dispose]: dispose
        });
        disposeOnce = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(this.registerEditor(editor), ()=>editor.setRootElement(null));
        return editor;
    }
    hasExtensionByName(name) {
        return this.extensionNameMap.has(name);
    }
    getExtensionRep(extension) {
        const rep = this.extensionNameMap.get(extension.name);
        if (rep) {
            if (!(rep.extension === extension)) {
                formatDevErrorMessage(`LexicalBuilder: A registered extension with name ${extension.name} exists but does not match the given extension`);
            }
            return rep;
        }
    }
    addEdge(fromExtensionName, toExtensionName, configs) {
        const outgoing = this.outgoingConfigEdges.get(fromExtensionName);
        if (outgoing) {
            outgoing.set(toExtensionName, configs);
        } else {
            this.outgoingConfigEdges.set(fromExtensionName, new Map([
                [
                    toExtensionName,
                    configs
                ]
            ]));
        }
        const incoming = this.incomingEdges.get(toExtensionName);
        if (incoming) {
            incoming.add(fromExtensionName);
        } else {
            this.incomingEdges.set(toExtensionName, new Set([
                fromExtensionName
            ]));
        }
    }
    addExtension(arg) {
        if (!(this._sortedExtensionReps === undefined)) {
            formatDevErrorMessage(`LexicalBuilder: addExtension called after finalization`);
        }
        const normalized = normalizeExtensionArgument(arg);
        const [extension] = normalized;
        if (!(typeof extension.name === 'string')) {
            formatDevErrorMessage(`LexicalBuilder: extension name must be string, not ${typeof extension.name}`);
        }
        let extensionRep = this.extensionNameMap.get(extension.name);
        if (!(extensionRep === undefined || extensionRep.extension === extension)) {
            formatDevErrorMessage(`LexicalBuilder: Multiple extensions registered with name ${extension.name}, names must be unique`);
        }
        if (!extensionRep) {
            extensionRep = new ExtensionRep(this, extension);
            this.extensionNameMap.set(extension.name, extensionRep);
            const hasConflict = this.conflicts.get(extension.name);
            if (typeof hasConflict === 'string') {
                {
                    formatDevErrorMessage(`LexicalBuilder: extension ${extension.name} conflicts with ${hasConflict}`);
                }
            }
            for (const name of extension.conflictsWith || []){
                if (!!this.extensionNameMap.has(name)) {
                    formatDevErrorMessage(`LexicalBuilder: extension ${extension.name} conflicts with ${name}`);
                }
                this.conflicts.set(name, extension.name);
            }
            for (const dep of extension.dependencies || []){
                const normDep = normalizeExtensionArgument(dep);
                this.addEdge(extension.name, normDep[0].name, normDep.slice(1));
                this.addExtension(normDep);
            }
            for (const [depName, config] of extension.peerDependencies || []){
                this.addEdge(extension.name, depName, config ? [
                    config
                ] : []);
            }
        }
    }
    sortedExtensionReps() {
        if (this._sortedExtensionReps) {
            return this._sortedExtensionReps;
        }
        // depth-first search based topological DAG sort
        // https://en.wikipedia.org/wiki/Topological_sorting
        const sortedExtensionReps = [];
        const visit = (rep, fromExtensionName)=>{
            let mark = rep.state;
            if (isExactlyPermanentExtensionRepState(mark)) {
                return;
            }
            const extensionName = rep.extension.name;
            if (!isExactlyUnmarkedExtensionRepState(mark)) {
                formatDevErrorMessage(`LexicalBuilder: Circular dependency detected for Extension ${extensionName} from ${fromExtensionName || '[unknown]'}`);
            }
            mark = applyTemporaryMark(mark);
            rep.state = mark;
            const outgoingConfigEdges = this.outgoingConfigEdges.get(extensionName);
            if (outgoingConfigEdges) {
                for (const toExtensionName of outgoingConfigEdges.keys()){
                    const toRep = this.extensionNameMap.get(toExtensionName);
                    // may be undefined for an optional peer dependency
                    if (toRep) {
                        visit(toRep, extensionName);
                    }
                }
            }
            mark = applyPermanentMark(mark);
            rep.state = mark;
            sortedExtensionReps.push(rep);
        };
        for (const rep of this.extensionNameMap.values()){
            if (isExactlyUnmarkedExtensionRepState(rep.state)) {
                visit(rep);
            }
        }
        for (const rep of sortedExtensionReps){
            for (const [toExtensionName, configs] of this.outgoingConfigEdges.get(rep.extension.name) || []){
                if (configs.length > 0) {
                    const toRep = this.extensionNameMap.get(toExtensionName);
                    if (toRep) {
                        for (const config of configs){
                            // eslint-disable-next-line @typescript-eslint/no-unsafe-argument -- any
                            toRep.configs.add(config);
                        }
                    }
                }
            }
        }
        for (const [extension, ...configs] of this.roots){
            if (configs.length > 0) {
                const toRep = this.extensionNameMap.get(extension.name);
                if (!(toRep !== undefined)) {
                    formatDevErrorMessage(`LexicalBuilder: Expecting existing ExtensionRep for ${extension.name}`);
                }
                for (const config of configs){
                    toRep.configs.add(config);
                }
            }
        }
        this._sortedExtensionReps = sortedExtensionReps;
        return this._sortedExtensionReps;
    }
    registerEditor(editor) {
        const extensionReps = this.sortedExtensionReps();
        const controller = new AbortController();
        const cleanups = [
            ()=>controller.abort()
        ];
        const signal = controller.signal;
        for (const extensionRep of extensionReps){
            const cleanup = extensionRep.register(editor, signal);
            if (cleanup) {
                cleanups.push(cleanup);
            }
        }
        for (const extensionRep of extensionReps){
            const cleanup = extensionRep.afterRegistration(editor);
            if (cleanup) {
                cleanups.push(cleanup);
            }
        }
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(...cleanups);
    }
    buildCreateEditorArgs() {
        const config = {};
        const nodes = new Set();
        const replacedNodes = new Map();
        const htmlExport = new Map();
        const htmlImport = {};
        const theme = {};
        const extensionReps = this.sortedExtensionReps();
        for (const extensionRep of extensionReps){
            const { extension } = extensionRep;
            if (extension.onError !== undefined) {
                config.onError = extension.onError;
            }
            if (extension.disableEvents !== undefined) {
                config.disableEvents = extension.disableEvents;
            }
            if (extension.parentEditor !== undefined) {
                config.parentEditor = extension.parentEditor;
            }
            if (extension.editable !== undefined) {
                config.editable = extension.editable;
            }
            if (extension.namespace !== undefined) {
                config.namespace = extension.namespace;
            }
            if (extension.$initialEditorState !== undefined) {
                config.$initialEditorState = extension.$initialEditorState;
            }
            if (extension.nodes) {
                for (const node of getNodeConfig(extension)){
                    if (typeof node !== 'function') {
                        const conflictExtension = replacedNodes.get(node.replace);
                        if (conflictExtension) {
                            {
                                formatDevErrorMessage(`LexicalBuilder: Extension ${extension.name} can not register replacement for node ${node.replace.name} because ${conflictExtension.extension.name} already did`);
                            }
                        }
                        replacedNodes.set(node.replace, extensionRep);
                    }
                    nodes.add(node);
                }
            }
            if (extension.html) {
                if (extension.html.export) {
                    for (const [k, v] of extension.html.export.entries()){
                        htmlExport.set(k, v);
                    }
                }
                if (extension.html.import) {
                    Object.assign(htmlImport, extension.html.import);
                }
            }
            if (extension.theme) {
                deepThemeMergeInPlace(theme, extension.theme);
            }
        }
        if (Object.keys(theme).length > 0) {
            config.theme = theme;
        }
        if (nodes.size) {
            config.nodes = [
                ...nodes
            ];
        }
        const hasImport = Object.keys(htmlImport).length > 0;
        const hasExport = htmlExport.size > 0;
        if (hasImport || hasExport) {
            config.html = {};
            if (hasImport) {
                config.html.import = htmlImport;
            }
            if (hasExport) {
                config.html.export = htmlExport;
            }
        }
        for (const extensionRep of extensionReps){
            extensionRep.init(config);
        }
        if (!config.onError) {
            config.onError = defaultOnError;
        }
        return config;
    }
}
/**
 * @experimental
 * Get the finalized config and output of an Extension that was used to build the editor.
 *
 * This is useful in the implementation of a LexicalNode or in other
 * situations where you have an editor reference but it's not easy to
 * pass the config or {@link ExtensionRegisterState} around.
 *
 * It will throw if the Editor was not built using this Extension.
 *
 * @param editor - The editor that was built using extension
 * @param extension - The concrete reference to an Extension used to build this editor
 * @returns The config and output for that Extension
 */ function getExtensionDependencyFromEditor(editor, extension) {
    const builder = LexicalBuilder.fromEditor(editor);
    const rep = builder.getExtensionRep(extension);
    if (!(rep !== undefined)) {
        formatDevErrorMessage(`getExtensionDependencyFromEditor: Extension ${extension.name} was not built when creating this editor`);
    }
    return rep.getExtensionDependency();
}
/**
 * @experimental
 * Get the finalized config and output of an Extension that was used to build the
 * editor by name.
 *
 * This can be used from the implementation of a LexicalNode or in other
 * situation where you have an editor reference but it's not easy to pass the
 * config around. Use this version if you do not have a concrete reference to
 * the Extension for some reason (e.g. it is an optional peer dependency, or you
 * are avoiding a circular import).
 *
 * Both the explicit Extension type and the name are required.
 *
 *  @example
 * ```tsx
 * import type { HistoryExtension } from "@lexical/history";
 * getPeerDependencyFromEditor<typeof HistoryExtension>(editor, "@lexical/history/History");
 * ```

 * @param editor - The editor that may have been built using extension
 * @param extensionName - The name of the Extension
 * @returns The config and output of the Extension or undefined
 */ function getPeerDependencyFromEditor(editor, extensionName) {
    const builder = LexicalBuilder.fromEditor(editor);
    const peer = builder.extensionNameMap.get(extensionName);
    return peer ? peer.getExtensionDependency() : undefined;
}
/**
 * Get the finalized config and output of an Extension that was used to build the
 * editor by name.
 *
 * This can be used from the implementation of a LexicalNode or in other
 * situation where you have an editor reference but it's not easy to pass the
 * config around. Use this version if you do not have a concrete reference to
 * the Extension for some reason (e.g. it is an optional peer dependency, or you
 * are avoiding a circular import).
 *
 * Both the explicit Extension type and the name are required.
 *
 *  @example
 * ```tsx
 * import type { EmojiExtension } from "./EmojiExtension";
 * export class EmojiNode extends TextNode {
 *   // other implementation details not included
 *   createDOM(
 *     config: EditorConfig,
 *     editor?: LexicalEditor | undefined
 *   ): HTMLElement {
 *     const dom = super.createDOM(config, editor);
 *     addClassNamesToElement(
 *       dom,
 *       getPeerDependencyFromEditorOrThrow<typeof EmojiExtension>(
 *         editor || $getEditor(),
 *         "@lexical/playground/emoji",
 *       ).config.emojiClass,
 *     );
 *     return dom;
 *   }
 * }
 * ```

 * @param editor - The editor that may have been built using extension
 * @param extensionName - The name of the Extension
 * @returns The config and output of the Extension
 */ function getPeerDependencyFromEditorOrThrow(editor, extensionName) {
    const dep = getPeerDependencyFromEditor(editor, extensionName);
    if (!(dep !== undefined)) {
        formatDevErrorMessage(`getPeerDependencyFromEditorOrThrow: Editor was not built with Extension ${extensionName}`);
    }
    return dep;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const EMPTY_SET = new Set();
/**
 * An extension that provides a `watchNodeKey` output that
 * returns a signal for the selection state of a node.
 *
 * Typically used for tracking whether a DecoratorNode is
 * currently selected or not. A framework independent
 * alternative to {@link useLexicalNodeSelection}.
 */ const NodeSelectionExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build (editor, config, state) {
        const editorStateStore = state.getDependency(EditorStateExtension).output;
        const watchedNodeStore = d({
            watchedNodeKeys: new Map()
        });
        const selectedNodeKeys = watchedSignal(()=>undefined, ()=>E(()=>{
                const prevSelectedNodeKeys = selectedNodeKeys.peek();
                const { watchedNodeKeys } = watchedNodeStore.value;
                let nextSelectedNodeKeys;
                let didChange = false;
                editorStateStore.value.read(()=>{
                    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
                    if (selection) {
                        for (const [key, listeners] of watchedNodeKeys.entries()){
                            if (listeners.size === 0) {
                                // We intentionally mutate this without firing a signal, to
                                // avoid re-triggering this effect. There are no subscribers
                                // so nothing can observe whether key was in the set or not
                                watchedNodeKeys.delete(key);
                                continue;
                            }
                            const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNodeByKey"])(key);
                            const isSelected = node && node.isSelected() || false;
                            didChange = didChange || isSelected !== (prevSelectedNodeKeys ? prevSelectedNodeKeys.has(key) : false);
                            if (isSelected) {
                                nextSelectedNodeKeys = nextSelectedNodeKeys || new Set();
                                nextSelectedNodeKeys.add(key);
                            }
                        }
                    }
                });
                if (!(!didChange && nextSelectedNodeKeys && prevSelectedNodeKeys && nextSelectedNodeKeys.size === prevSelectedNodeKeys.size)) {
                    selectedNodeKeys.value = nextSelectedNodeKeys;
                }
            }));
        function watchNodeKey(key) {
            const watcher = w(()=>(selectedNodeKeys.value || EMPTY_SET).has(key));
            const { watchedNodeKeys } = watchedNodeStore.peek();
            let listeners = watchedNodeKeys.get(key);
            const hadListener = listeners !== undefined;
            listeners = listeners || new Set();
            listeners.add(watcher);
            if (!hadListener) {
                watchedNodeKeys.set(key, listeners);
                watchedNodeStore.value = {
                    watchedNodeKeys
                };
            }
            return watcher;
        }
        return {
            watchNodeKey
        };
    },
    dependencies: [
        EditorStateExtension
    ],
    name: '@lexical/extension/NodeSelection'
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const INSERT_HORIZONTAL_RULE_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('INSERT_HORIZONTAL_RULE_COMMAND');
class HorizontalRuleNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DecoratorNode"] {
    static getType() {
        return 'horizontalrule';
    }
    static clone(node) {
        return new HorizontalRuleNode(node.__key);
    }
    static importJSON(serializedNode) {
        return $createHorizontalRuleNode().updateFromJSON(serializedNode);
    }
    static importDOM() {
        return {
            hr: ()=>({
                    conversion: $convertHorizontalRuleElement,
                    priority: 0
                })
        };
    }
    exportDOM() {
        return {
            element: document.createElement('hr')
        };
    }
    createDOM(config) {
        const element = document.createElement('hr');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(element, config.theme.hr);
        return element;
    }
    getTextContent() {
        return '\n';
    }
    isInline() {
        return false;
    }
    updateDOM() {
        return false;
    }
}
function $convertHorizontalRuleElement() {
    return {
        node: $createHorizontalRuleNode()
    };
}
function $createHorizontalRuleNode() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$create"])(HorizontalRuleNode);
}
function $isHorizontalRuleNode(node) {
    return node instanceof HorizontalRuleNode;
}
function $toggleNodeSelection(node, shiftKey = false) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    const wasSelected = node.isSelected();
    const key = node.getKey();
    let nodeSelection;
    if (shiftKey && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
        nodeSelection = selection;
    } else {
        nodeSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createNodeSelection"])();
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelection"])(nodeSelection);
    }
    if (wasSelected) {
        nodeSelection.delete(key);
    } else {
        nodeSelection.add(key);
    }
}
/**
 * An extension for HorizontalRuleNode that provides an implementation that
 * works without any React dependency.
 */ const HorizontalRuleExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    dependencies: [
        EditorStateExtension,
        NodeSelectionExtension
    ],
    name: '@lexical/extension/HorizontalRule',
    nodes: ()=>[
            HorizontalRuleNode
        ],
    register (editor, config, state) {
        const { watchNodeKey } = state.getDependency(NodeSelectionExtension).output;
        const nodeSelectionStore = d({
            nodeSelections: new Map()
        });
        const isSelectedClassName = editor._config.theme.hrSelected ?? 'selected';
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CLICK_COMMAND"], (event)=>{
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isDOMNode"])(event.target)) {
                const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNodeFromDOMNode"])(event.target);
                if ($isHorizontalRuleNode(node)) {
                    $toggleNodeSelection(node, event.shiftKey);
                    return true;
                }
            }
            return false;
        }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerMutationListener(HorizontalRuleNode, (nodes, payload)=>{
            o(()=>{
                let didChange = false;
                const { nodeSelections } = nodeSelectionStore.peek();
                for (const [k, v] of nodes.entries()){
                    if (v === 'destroyed') {
                        nodeSelections.delete(k);
                        didChange = true;
                    } else {
                        const prev = nodeSelections.get(k);
                        const dom = editor.getElementByKey(k);
                        if (prev) {
                            prev.domNode.value = dom;
                        } else {
                            didChange = true;
                            nodeSelections.set(k, {
                                domNode: d(dom),
                                selectedSignal: watchNodeKey(k)
                            });
                        }
                    }
                }
                if (didChange) {
                    nodeSelectionStore.value = {
                        nodeSelections
                    };
                }
            });
        }), E(()=>{
            const effects = [];
            for (const { domNode, selectedSignal } of nodeSelectionStore.value.nodeSelections.values()){
                effects.push(E(()=>{
                    const dom = domNode.value;
                    if (dom) {
                        const isSelected = selectedSignal.value;
                        if (isSelected) {
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(dom, isSelectedClassName);
                        } else {
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["removeClassNamesFromElement"])(dom, isSelectedClassName);
                        }
                    }
                }));
            }
            return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(...effects);
        }));
    }
});
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function $indentOverTab(selection) {
    // const handled = new Set();
    const nodes = selection.getNodes();
    const canIndentBlockNodes = nodes.filter((node)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isBlockElementNode"])(node) && node.canIndent());
    // 1. If selection spans across canIndent block nodes: indent
    if (canIndentBlockNodes.length > 0) {
        return true;
    }
    // 2. If first (anchor/focus) is at block start: indent
    const anchor = selection.anchor;
    const focus = selection.focus;
    const first = focus.isBefore(anchor) ? focus : anchor;
    const firstNode = first.getNode();
    const firstBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$getNearestBlockElementAncestorOrThrow"])(firstNode);
    if (firstBlock.canIndent()) {
        const firstBlockKey = firstBlock.getKey();
        let selectionAtStart = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createRangeSelection"])();
        selectionAtStart.anchor.set(firstBlockKey, 0, 'element');
        selectionAtStart.focus.set(firstBlockKey, 0, 'element');
        selectionAtStart = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$normalizeSelection__EXPERIMENTAL"])(selectionAtStart);
        if (selectionAtStart.anchor.is(first)) {
            return true;
        }
    }
    // 3. Else: tab
    return false;
}
function $defaultCanIndent(node) {
    return node.canBeEmpty();
}
function registerTabIndentation(editor, maxIndent, $canIndent = $defaultCanIndent) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_TAB_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        event.preventDefault();
        const command = $indentOverTab(selection) ? event.shiftKey ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["OUTDENT_CONTENT_COMMAND"] : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INDENT_CONTENT_COMMAND"] : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_TAB_COMMAND"];
        return editor.dispatchCommand(command, undefined);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INDENT_CONTENT_COMMAND"], ()=>{
        const currentMaxIndent = typeof maxIndent === 'number' ? maxIndent : maxIndent ? maxIndent.peek() : null;
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        const $currentCanIndent = typeof $canIndent === 'function' ? $canIndent : $canIndent.peek();
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$handleIndentAndOutdent"])((block)=>{
            if ($currentCanIndent(block)) {
                const newIndent = block.getIndent() + 1;
                if (!currentMaxIndent || newIndent < currentMaxIndent) {
                    block.setIndent(newIndent);
                }
            }
        });
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_CRITICAL"]));
}
/**
 * This extension adds the ability to indent content using the tab key. Generally, we don't
 * recommend using this plugin as it could negatively affect accessibility for keyboard
 * users, causing focus to become trapped within the editor.
 */ const TabIndentationExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build (editor, config, state) {
        return namedSignals(config);
    },
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        $canIndent: $defaultCanIndent,
        disabled: false,
        maxIndent: null
    }),
    name: '@lexical/extension/TabIndentation',
    register (editor, config, state) {
        const { disabled, maxIndent, $canIndent } = state.getOutput();
        return E(()=>{
            if (!disabled.value) {
                return registerTabIndentation(editor, maxIndent, $canIndent);
            }
        });
    }
});
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/html/LexicalHtml.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$generateHtmlFromNodes",
    ()=>$generateHtmlFromNodes,
    "$generateNodesFromDOM",
    ()=>$generateNodesFromDOM
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
;
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /**
 * How you parse your html string to get a document is left up to you. In the browser you can use the native
 * DOMParser API to generate a document (see clipboard.ts), but to use in a headless environment you can use JSDom
 * or an equivalent library and pass in the document here.
 */ function $generateNodesFromDOM(editor, dom) {
    const elements = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isDOMDocumentNode"])(dom) ? dom.body.childNodes : dom.childNodes;
    let lexicalNodes = [];
    const allArtificialNodes = [];
    for (const element of elements){
        if (!IGNORE_TAGS.has(element.nodeName)) {
            const lexicalNode = $createNodesFromDOM(element, editor, allArtificialNodes, false);
            if (lexicalNode !== null) {
                lexicalNodes = lexicalNodes.concat(lexicalNode);
            }
        }
    }
    $unwrapArtificialNodes(allArtificialNodes);
    return lexicalNodes;
}
function $generateHtmlFromNodes(editor, selection) {
    if (typeof document === 'undefined' || ("TURBOPACK compile-time value", "undefined") === 'undefined' && typeof /*TURBOPACK member replacement*/ __turbopack_context__.g.window === 'undefined') {
        throw new Error('To use $generateHtmlFromNodes in headless mode please initialize a headless browser implementation such as JSDom before calling this function.');
    }
    const container = document.createElement('div');
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])();
    const topLevelChildren = root.getChildren();
    for(let i = 0; i < topLevelChildren.length; i++){
        const topLevelNode = topLevelChildren[i];
        $appendNodesToHTML(editor, topLevelNode, container, selection);
    }
    return container.innerHTML;
}
function $appendNodesToHTML(editor, currentNode, parentElement, selection = null) {
    let shouldInclude = selection !== null ? currentNode.isSelected(selection) : true;
    const shouldExclude = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode) && currentNode.excludeFromCopy('html');
    let target = currentNode;
    if (selection !== null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(currentNode)) {
        target = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$sliceSelectedTextNodeContent"])(selection, currentNode, 'clone');
    }
    const children = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(target) ? target.getChildren() : [];
    const registeredNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getRegisteredNode"])(editor, target.getType());
    let exportOutput;
    // Use HTMLConfig overrides, if available.
    if (registeredNode && registeredNode.exportDOM !== undefined) {
        exportOutput = registeredNode.exportDOM(editor, target);
    } else {
        exportOutput = target.exportDOM(editor);
    }
    const { element, after } = exportOutput;
    if (!element) {
        return false;
    }
    const fragment = document.createDocumentFragment();
    for(let i = 0; i < children.length; i++){
        const childNode = children[i];
        const shouldIncludeChild = $appendNodesToHTML(editor, childNode, fragment, selection);
        if (!shouldInclude && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode) && shouldIncludeChild && currentNode.extractWithChild(childNode, selection, 'html')) {
            shouldInclude = true;
        }
    }
    if (shouldInclude && !shouldExclude) {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(element) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isDocumentFragment"])(element)) {
            element.append(fragment);
        }
        parentElement.append(element);
        if (after) {
            const newElement = after.call(target, element);
            if (newElement) {
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isDocumentFragment"])(element)) {
                    element.replaceChildren(newElement);
                } else {
                    element.replaceWith(newElement);
                }
            }
        }
    } else {
        parentElement.append(fragment);
    }
    return shouldInclude;
}
function getConversionFunction(domNode, editor) {
    const { nodeName } = domNode;
    const cachedConversions = editor._htmlConversions.get(nodeName.toLowerCase());
    let currentConversion = null;
    if (cachedConversions !== undefined) {
        for (const cachedConversion of cachedConversions){
            const domConversion = cachedConversion(domNode);
            if (domConversion !== null && (currentConversion === null || // Given equal priority, prefer the last registered importer
            // which is typically an application custom node or HTMLConfig['import']
            (currentConversion.priority || 0) <= (domConversion.priority || 0))) {
                currentConversion = domConversion;
            }
        }
    }
    return currentConversion !== null ? currentConversion.conversion : null;
}
const IGNORE_TAGS = new Set([
    'STYLE',
    'SCRIPT'
]);
function $createNodesFromDOM(node, editor, allArtificialNodes, hasBlockAncestorLexicalNode, forChildMap = new Map(), parentLexicalNode) {
    let lexicalNodes = [];
    if (IGNORE_TAGS.has(node.nodeName)) {
        return lexicalNodes;
    }
    let currentLexicalNode = null;
    const transformFunction = getConversionFunction(node, editor);
    const transformOutput = transformFunction ? transformFunction(node) : null;
    let postTransform = null;
    if (transformOutput !== null) {
        postTransform = transformOutput.after;
        const transformNodes = transformOutput.node;
        currentLexicalNode = Array.isArray(transformNodes) ? transformNodes[transformNodes.length - 1] : transformNodes;
        if (currentLexicalNode !== null) {
            for (const [, forChildFunction] of forChildMap){
                currentLexicalNode = forChildFunction(currentLexicalNode, parentLexicalNode);
                if (!currentLexicalNode) {
                    break;
                }
            }
            if (currentLexicalNode) {
                lexicalNodes.push(...Array.isArray(transformNodes) ? transformNodes : [
                    currentLexicalNode
                ]);
            }
        }
        if (transformOutput.forChild != null) {
            forChildMap.set(node.nodeName, transformOutput.forChild);
        }
    }
    // If the DOM node doesn't have a transformer, we don't know what
    // to do with it but we still need to process any childNodes.
    const children = node.childNodes;
    let childLexicalNodes = [];
    const hasBlockAncestorLexicalNodeForChildren = currentLexicalNode != null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(currentLexicalNode) ? false : currentLexicalNode != null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isBlockElementNode"])(currentLexicalNode) || hasBlockAncestorLexicalNode;
    for(let i = 0; i < children.length; i++){
        childLexicalNodes.push(...$createNodesFromDOM(children[i], editor, allArtificialNodes, hasBlockAncestorLexicalNodeForChildren, new Map(forChildMap), currentLexicalNode));
    }
    if (postTransform != null) {
        childLexicalNodes = postTransform(childLexicalNodes);
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isBlockDomNode"])(node)) {
        if (!hasBlockAncestorLexicalNodeForChildren) {
            childLexicalNodes = wrapContinuousInlines(node, childLexicalNodes, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"]);
        } else {
            childLexicalNodes = wrapContinuousInlines(node, childLexicalNodes, ()=>{
                const artificialNode = new __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ArtificialNode__DO_NOT_USE"]();
                allArtificialNodes.push(artificialNode);
                return artificialNode;
            });
        }
    }
    if (currentLexicalNode == null) {
        if (childLexicalNodes.length > 0) {
            // If it hasn't been converted to a LexicalNode, we hoist its children
            // up to the same level as it.
            lexicalNodes = lexicalNodes.concat(childLexicalNodes);
        } else {
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isBlockDomNode"])(node) && isDomNodeBetweenTwoInlineNodes(node)) {
                // Empty block dom node that hasnt been converted, we replace it with a linebreak if its between inline nodes
                lexicalNodes = lexicalNodes.concat((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createLineBreakNode"])());
            }
        }
    } else {
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentLexicalNode)) {
            // If the current node is a ElementNode after conversion,
            // we can append all the children to it.
            currentLexicalNode.append(...childLexicalNodes);
        }
    }
    return lexicalNodes;
}
function wrapContinuousInlines(domNode, nodes, createWrapperFn) {
    const textAlign = domNode.style.textAlign;
    const out = [];
    let continuousInlines = [];
    // wrap contiguous inline child nodes in para
    for(let i = 0; i < nodes.length; i++){
        const node = nodes[i];
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isBlockElementNode"])(node)) {
            if (textAlign && !node.getFormat()) {
                node.setFormat(textAlign);
            }
            out.push(node);
        } else {
            continuousInlines.push(node);
            if (i === nodes.length - 1 || i < nodes.length - 1 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isBlockElementNode"])(nodes[i + 1])) {
                const wrapper = createWrapperFn();
                wrapper.setFormat(textAlign);
                wrapper.append(...continuousInlines);
                out.push(wrapper);
                continuousInlines = [];
            }
        }
    }
    return out;
}
function $unwrapArtificialNodes(allArtificialNodes) {
    for (const node of allArtificialNodes){
        if (node.getNextSibling() instanceof __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ArtificialNode__DO_NOT_USE"]) {
            node.insertAfter((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createLineBreakNode"])());
        }
    }
    // Replace artificial node with it's children
    for (const node of allArtificialNodes){
        const children = node.getChildren();
        for (const child of children){
            node.insertBefore(child);
        }
        node.remove();
    }
}
function isDomNodeBetweenTwoInlineNodes(node) {
    if (node.nextSibling == null || node.previousSibling == null) {
        return false;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isInlineDomNode"])(node.nextSibling) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isInlineDomNode"])(node.previousSibling);
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/list/LexicalList.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$createListItemNode",
    ()=>$createListItemNode,
    "$createListNode",
    ()=>$createListNode,
    "$getListDepth",
    ()=>$getListDepth,
    "$handleListInsertParagraph",
    ()=>$handleListInsertParagraph,
    "$insertList",
    ()=>$insertList,
    "$isListItemNode",
    ()=>$isListItemNode,
    "$isListNode",
    ()=>$isListNode,
    "$removeList",
    ()=>$removeList,
    "CheckListExtension",
    ()=>CheckListExtension,
    "INSERT_CHECK_LIST_COMMAND",
    ()=>INSERT_CHECK_LIST_COMMAND,
    "INSERT_ORDERED_LIST_COMMAND",
    ()=>INSERT_ORDERED_LIST_COMMAND,
    "INSERT_UNORDERED_LIST_COMMAND",
    ()=>INSERT_UNORDERED_LIST_COMMAND,
    "ListExtension",
    ()=>ListExtension,
    "ListItemNode",
    ()=>ListItemNode,
    "ListNode",
    ()=>ListNode,
    "REMOVE_LIST_COMMAND",
    ()=>REMOVE_LIST_COMMAND,
    "UPDATE_LIST_START_COMMAND",
    ()=>UPDATE_LIST_START_COMMAND,
    "insertList",
    ()=>insertList,
    "registerCheckList",
    ()=>registerCheckList,
    "registerList",
    ()=>registerList,
    "registerListStrictIndentTransform",
    ()=>registerListStrictIndentTransform,
    "removeList",
    ()=>removeList
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/extension/LexicalExtension.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/utils/LexicalUtils.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>");
;
;
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ // Do not require this module directly! Use normal `invariant` calls.
function formatDevErrorMessage(message) {
    throw new Error(message);
}
/**
 * Checks the depth of listNode from the root node.
 * @param listNode - The ListNode to be checked.
 * @returns The depth of the ListNode.
 */ function $getListDepth(listNode) {
    let depth = 1;
    let parent = listNode.getParent();
    while(parent != null){
        if ($isListItemNode(parent)) {
            const parentList = parent.getParent();
            if ($isListNode(parentList)) {
                depth++;
                parent = parentList.getParent();
                continue;
            }
            {
                formatDevErrorMessage(`A ListItemNode must have a ListNode for a parent.`);
            }
        }
        return depth;
    }
    return depth;
}
/**
 * Finds the nearest ancestral ListNode and returns it, throws an invariant if listItem is not a ListItemNode.
 * @param listItem - The node to be checked.
 * @returns The ListNode found.
 */ function $getTopListNode(listItem) {
    let list = listItem.getParent();
    if (!$isListNode(list)) {
        {
            formatDevErrorMessage(`A ListItemNode must have a ListNode for a parent.`);
        }
    }
    let parent = list;
    while(parent !== null){
        parent = parent.getParent();
        if ($isListNode(parent)) {
            list = parent;
        }
    }
    return list;
}
/**
 * A recursive Depth-First Search (Postorder Traversal) that finds all of a node's children
 * that are of type ListItemNode and returns them in an array.
 * @param node - The ListNode to start the search.
 * @returns An array containing all nodes of type ListItemNode found.
 */ // This should probably be $getAllChildrenOfType
function $getAllListItems(node) {
    let listItemNodes = [];
    const listChildren = node.getChildren().filter($isListItemNode);
    for(let i = 0; i < listChildren.length; i++){
        const listItemNode = listChildren[i];
        const firstChild = listItemNode.getFirstChild();
        if ($isListNode(firstChild)) {
            listItemNodes = listItemNodes.concat($getAllListItems(firstChild));
        } else {
            listItemNodes.push(listItemNode);
        }
    }
    return listItemNodes;
}
/**
 * Checks to see if the passed node is a ListItemNode and has a ListNode as a child.
 * @param node - The node to be checked.
 * @returns true if the node is a ListItemNode and has a ListNode child, false otherwise.
 */ function isNestedListNode(node) {
    return $isListItemNode(node) && $isListNode(node.getFirstChild());
}
/**
 * Takes a deeply nested ListNode or ListItemNode and traverses up the branch to delete the first
 * ancestral ListNode (which could be the root ListNode) or ListItemNode with siblings, essentially
 * bringing the deeply nested node up the branch once. Would remove sublist if it has siblings.
 * Should not break ListItem -> List -> ListItem chain as empty List/ItemNodes should be removed on .remove().
 * @param sublist - The nested ListNode or ListItemNode to be brought up the branch.
 */ function $removeHighestEmptyListParent(sublist) {
    // Nodes may be repeatedly indented, to create deeply nested lists that each
    // contain just one bullet.
    // Our goal is to remove these (empty) deeply nested lists. The easiest
    // way to do that is crawl back up the tree until we find a node that has siblings
    // (e.g. is actually part of the list contents) and delete that, or delete
    // the root of the list (if no list nodes have siblings.)
    let emptyListPtr = sublist;
    while(emptyListPtr.getNextSibling() == null && emptyListPtr.getPreviousSibling() == null){
        const parent = emptyListPtr.getParent();
        if (parent == null || !($isListItemNode(parent) || $isListNode(parent))) {
            break;
        }
        emptyListPtr = parent;
    }
    emptyListPtr.remove();
}
/**
 * Wraps a node into a ListItemNode.
 * @param node - The node to be wrapped into a ListItemNode
 * @returns The ListItemNode which the passed node is wrapped in.
 */ function $wrapInListItem(node) {
    const listItemWrapper = $createListItemNode();
    return listItemWrapper.append(node);
}
/**
 * Calculates the start value for a new list created by splitting an existing list.
 */ function $getNewListStart(list, listItem) {
    return list.getStart() + listItem.getIndexWithinParent();
}
function $isSelectingEmptyListItem(anchorNode, nodes) {
    return $isListItemNode(anchorNode) && (nodes.length === 0 || nodes.length === 1 && anchorNode.is(nodes[0]) && anchorNode.getChildrenSize() === 0);
}
/**
 * Inserts a new ListNode. If the selection's anchor node is an empty ListItemNode and is a child of
 * the root/shadow root, it will replace the ListItemNode with a ListNode and the old ListItemNode.
 * Otherwise it will replace its parent with a new ListNode and re-insert the ListItemNode and any previous children.
 * If the selection's anchor node is not an empty ListItemNode, it will add a new ListNode or merge an existing ListNode,
 * unless the the node is a leaf node, in which case it will attempt to find a ListNode up the branch and replace it with
 * a new ListNode, or create a new ListNode at the nearest root/shadow root.
 * @param listType - The type of list, "number" | "bullet" | "check".
 */ function $insertList(listType) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if (selection !== null) {
        let nodes = selection.getNodes();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            const anchorAndFocus = selection.getStartEndPoints();
            if (!(anchorAndFocus !== null)) {
                formatDevErrorMessage(`insertList: anchor should be defined`);
            }
            const [anchor] = anchorAndFocus;
            const anchorNode = anchor.getNode();
            const anchorNodeParent = anchorNode.getParent();
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(anchorNode)) {
                const firstChild = anchorNode.getFirstChild();
                if (firstChild) {
                    nodes = firstChild.selectStart().getNodes();
                } else {
                    const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
                    anchorNode.append(paragraph);
                    nodes = paragraph.select().getNodes();
                }
            } else if ($isSelectingEmptyListItem(anchorNode, nodes)) {
                const list = $createListNode(listType);
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(anchorNodeParent)) {
                    anchorNode.replace(list);
                    const listItem = $createListItemNode();
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(anchorNode)) {
                        listItem.setFormat(anchorNode.getFormatType());
                        listItem.setIndent(anchorNode.getIndent());
                    }
                    list.append(listItem);
                } else if ($isListItemNode(anchorNode)) {
                    const parent = anchorNode.getParentOrThrow();
                    append(list, parent.getChildren());
                    parent.replace(list);
                }
                return;
            }
        }
        const handled = new Set();
        for(let i = 0; i < nodes.length; i++){
            const node = nodes[i];
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && node.isEmpty() && !$isListItemNode(node) && !handled.has(node.getKey())) {
                $createListOrMerge(node, listType);
                continue;
            }
            let parent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isLeafNode"])(node) ? node.getParent() : $isListItemNode(node) && node.isEmpty() ? node : null;
            while(parent != null){
                const parentKey = parent.getKey();
                if ($isListNode(parent)) {
                    if (!handled.has(parentKey)) {
                        const newListNode = $createListNode(listType);
                        append(newListNode, parent.getChildren());
                        parent.replace(newListNode);
                        handled.add(parentKey);
                    }
                    break;
                } else {
                    const nextParent = parent.getParent();
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(nextParent) && !handled.has(parentKey)) {
                        handled.add(parentKey);
                        $createListOrMerge(parent, listType);
                        break;
                    }
                    parent = nextParent;
                }
            }
        }
    }
}
function append(node, nodesToAppend) {
    node.splice(node.getChildrenSize(), 0, nodesToAppend);
}
function $createListOrMerge(node, listType) {
    if ($isListNode(node)) {
        return node;
    }
    const previousSibling = node.getPreviousSibling();
    const nextSibling = node.getNextSibling();
    const listItem = $createListItemNode();
    append(listItem, node.getChildren());
    let targetList;
    if ($isListNode(previousSibling) && listType === previousSibling.getListType()) {
        previousSibling.append(listItem);
        // if the same type of list is on both sides, merge them.
        if ($isListNode(nextSibling) && listType === nextSibling.getListType()) {
            append(previousSibling, nextSibling.getChildren());
            nextSibling.remove();
        }
        targetList = previousSibling;
    } else if ($isListNode(nextSibling) && listType === nextSibling.getListType()) {
        nextSibling.getFirstChildOrThrow().insertBefore(listItem);
        targetList = nextSibling;
    } else {
        const list = $createListNode(listType);
        list.append(listItem);
        node.replace(list);
        targetList = list;
    }
    // listItem needs to be attached to root prior to setting indent
    listItem.setFormat(node.getFormatType());
    listItem.setIndent(node.getIndent());
    // Preserve element-anchored selections by updating them to anchor to the listItem instead of the listNode.
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        if (targetList.getKey() === selection.anchor.key) {
            selection.anchor.set(listItem.getKey(), selection.anchor.offset, 'element');
        }
        if (targetList.getKey() === selection.focus.key) {
            selection.focus.set(listItem.getKey(), selection.focus.offset, 'element');
        }
    }
    node.remove();
    return targetList;
}
/**
 * A recursive function that goes through each list and their children, including nested lists,
 * appending list2 children after list1 children and updating ListItemNode values.
 * @param list1 - The first list to be merged.
 * @param list2 - The second list to be merged.
 */ function mergeLists(list1, list2) {
    const listItem1 = list1.getLastChild();
    const listItem2 = list2.getFirstChild();
    if (listItem1 && listItem2 && isNestedListNode(listItem1) && isNestedListNode(listItem2)) {
        mergeLists(listItem1.getFirstChild(), listItem2.getFirstChild());
        listItem2.remove();
    }
    const toMerge = list2.getChildren();
    if (toMerge.length > 0) {
        list1.append(...toMerge);
    }
    list2.remove();
}
/**
 * Searches for the nearest ancestral ListNode and removes it. If selection is an empty ListItemNode
 * it will remove the whole list, including the ListItemNode. For each ListItemNode in the ListNode,
 * removeList will also generate new ParagraphNodes in the removed ListNode's place. Any child node
 * inside a ListItemNode will be appended to the new ParagraphNodes.
 */ function $removeList() {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        const listNodes = new Set();
        const nodes = selection.getNodes();
        const anchorNode = selection.anchor.getNode();
        if ($isSelectingEmptyListItem(anchorNode, nodes)) {
            listNodes.add($getTopListNode(anchorNode));
        } else {
            for(let i = 0; i < nodes.length; i++){
                const node = nodes[i];
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isLeafNode"])(node)) {
                    const listItemNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$getNearestNodeOfType"])(node, ListItemNode);
                    if (listItemNode != null) {
                        listNodes.add($getTopListNode(listItemNode));
                    }
                }
            }
        }
        for (const listNode of listNodes){
            let insertionPoint = listNode;
            const listItems = $getAllListItems(listNode);
            for (const listItemNode of listItems){
                const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])().setTextStyle(selection.style).setTextFormat(selection.format);
                append(paragraph, listItemNode.getChildren());
                insertionPoint.insertAfter(paragraph);
                insertionPoint = paragraph;
                // When the anchor and focus fall on the textNode
                // we don't have to change the selection because the textNode will be appended to
                // the newly generated paragraph.
                // When selection is in empty nested list item, selection is actually on the listItemNode.
                // When the corresponding listItemNode is deleted and replaced by the newly generated paragraph
                // we should manually set the selection's focus and anchor to the newly generated paragraph.
                if (listItemNode.__key === selection.anchor.key) {
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setPointFromCaret"])(selection.anchor, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$normalizeCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(paragraph, 'next')));
                }
                if (listItemNode.__key === selection.focus.key) {
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setPointFromCaret"])(selection.focus, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$normalizeCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(paragraph, 'next')));
                }
                listItemNode.remove();
            }
            listNode.remove();
        }
    }
}
/**
 * Takes the value of a child ListItemNode and makes it the value the ListItemNode
 * should be if it isn't already. Also ensures that checked is undefined if the
 * parent does not have a list type of 'check'.
 * @param list - The list whose children are updated.
 */ function updateChildrenListItemValue(list) {
    const isNotChecklist = list.getListType() !== 'check';
    let value = list.getStart();
    for (const child of list.getChildren()){
        if ($isListItemNode(child)) {
            if (child.getValue() !== value) {
                child.setValue(value);
            }
            if (isNotChecklist && child.getLatest().__checked != null) {
                child.setChecked(undefined);
            }
            if (!$isListNode(child.getFirstChild())) {
                value++;
            }
        }
    }
}
/**
 * Merge the next sibling list if same type.
 * <ul> will merge with <ul>, but NOT <ul> with <ol>.
 * @param list - The list whose next sibling should be potentially merged
 */ function mergeNextSiblingListIfSameType(list) {
    const nextSibling = list.getNextSibling();
    if ($isListNode(nextSibling) && list.getListType() === nextSibling.getListType()) {
        mergeLists(list, nextSibling);
    }
}
/**
 * Adds an empty ListNode/ListItemNode chain at listItemNode, so as to
 * create an indent effect. Won't indent ListItemNodes that have a ListNode as
 * a child, but does merge sibling ListItemNodes if one has a nested ListNode.
 * @param listItemNode - The ListItemNode to be indented.
 */ function $handleIndent(listItemNode) {
    // go through each node and decide where to move it.
    const removed = new Set();
    if (isNestedListNode(listItemNode) || removed.has(listItemNode.getKey())) {
        return;
    }
    const parent = listItemNode.getParent();
    // We can cast both of the below `isNestedListNode` only returns a boolean type instead of a user-defined type guards
    const nextSibling = listItemNode.getNextSibling();
    const previousSibling = listItemNode.getPreviousSibling();
    // if there are nested lists on either side, merge them all together.
    if (isNestedListNode(nextSibling) && isNestedListNode(previousSibling)) {
        const innerList = previousSibling.getFirstChild();
        if ($isListNode(innerList)) {
            innerList.append(listItemNode);
            const nextInnerList = nextSibling.getFirstChild();
            if ($isListNode(nextInnerList)) {
                const children = nextInnerList.getChildren();
                append(innerList, children);
                nextSibling.remove();
                removed.add(nextSibling.getKey());
            }
        }
    } else if (isNestedListNode(nextSibling)) {
        // if the ListItemNode is next to a nested ListNode, merge them
        const innerList = nextSibling.getFirstChild();
        if ($isListNode(innerList)) {
            const firstChild = innerList.getFirstChild();
            if (firstChild !== null) {
                firstChild.insertBefore(listItemNode);
            }
        }
    } else if (isNestedListNode(previousSibling)) {
        const innerList = previousSibling.getFirstChild();
        if ($isListNode(innerList)) {
            innerList.append(listItemNode);
        }
    } else {
        // otherwise, we need to create a new nested ListNode
        if ($isListNode(parent)) {
            const newListItem = $createListItemNode().setTextFormat(listItemNode.getTextFormat()).setTextStyle(listItemNode.getTextStyle());
            const newList = $createListNode(parent.getListType()).setTextFormat(parent.getTextFormat()).setTextStyle(parent.getTextStyle());
            newListItem.append(newList);
            newList.append(listItemNode);
            if (previousSibling) {
                previousSibling.insertAfter(newListItem);
            } else if (nextSibling) {
                nextSibling.insertBefore(newListItem);
            } else {
                parent.append(newListItem);
            }
        }
    }
}
/**
 * Removes an indent by removing an empty ListNode/ListItemNode chain. An indented ListItemNode
 * has a great grandparent node of type ListNode, which is where the ListItemNode will reside
 * within as a child.
 * @param listItemNode - The ListItemNode to remove the indent (outdent).
 */ function $handleOutdent(listItemNode) {
    // go through each node and decide where to move it.
    if (isNestedListNode(listItemNode)) {
        return;
    }
    const parentList = listItemNode.getParent();
    const grandparentListItem = parentList ? parentList.getParent() : undefined;
    const greatGrandparentList = grandparentListItem ? grandparentListItem.getParent() : undefined;
    // If it doesn't have these ancestors, it's not indented.
    if ($isListNode(greatGrandparentList) && $isListItemNode(grandparentListItem) && $isListNode(parentList)) {
        // if it's the first child in it's parent list, insert it into the
        // great grandparent list before the grandparent
        const firstChild = parentList ? parentList.getFirstChild() : undefined;
        const lastChild = parentList ? parentList.getLastChild() : undefined;
        if (listItemNode.is(firstChild)) {
            grandparentListItem.insertBefore(listItemNode);
            if (parentList.isEmpty()) {
                grandparentListItem.remove();
            }
        // if it's the last child in it's parent list, insert it into the
        // great grandparent list after the grandparent.
        } else if (listItemNode.is(lastChild)) {
            grandparentListItem.insertAfter(listItemNode);
            if (parentList.isEmpty()) {
                grandparentListItem.remove();
            }
        } else {
            // otherwise, we need to split the siblings into two new nested lists
            const listType = parentList.getListType();
            const previousSiblingsListItem = $createListItemNode();
            const previousSiblingsList = $createListNode(listType);
            previousSiblingsListItem.append(previousSiblingsList);
            listItemNode.getPreviousSiblings().forEach((sibling)=>previousSiblingsList.append(sibling));
            const nextSiblingsListItem = $createListItemNode();
            const nextSiblingsList = $createListNode(listType);
            nextSiblingsListItem.append(nextSiblingsList);
            append(nextSiblingsList, listItemNode.getNextSiblings());
            // put the sibling nested lists on either side of the grandparent list item in the great grandparent.
            grandparentListItem.insertBefore(previousSiblingsListItem);
            grandparentListItem.insertAfter(nextSiblingsListItem);
            // replace the grandparent list item (now between the siblings) with the outdented list item.
            grandparentListItem.replace(listItemNode);
        }
    }
}
/**
 * Attempts to insert a ParagraphNode at selection and selects the new node. The selection must contain a ListItemNode
 * or a node that does not already contain text. If its grandparent is the root/shadow root, it will get the ListNode
 * (which should be the parent node) and insert the ParagraphNode as a sibling to the ListNode. If the ListNode is
 * nested in a ListItemNode instead, it will add the ParagraphNode after the grandparent ListItemNode.
 * Throws an invariant if the selection is not a child of a ListNode.
 * @returns true if a ParagraphNode was inserted successfully, false if there is no selection
 * or the selection does not contain a ListItemNode or the node already holds text.
 */ function $handleListInsertParagraph(restoreNumbering = false) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) || !selection.isCollapsed()) {
        return false;
    }
    // Only run this code on empty list items (including whitespace-only)
    const anchor = selection.anchor.getNode();
    let listItem = null;
    if ($isListItemNode(anchor) && anchor.getChildrenSize() === 0) {
        // Truly empty list item (element selection)
        listItem = anchor;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(anchor)) {
        // Check if the entire list item contains only whitespace text nodes
        const parentListItem = anchor.getParent();
        if ($isListItemNode(parentListItem) && parentListItem.getChildren().every((node)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(node) && node.getTextContent().trim() === '')) {
            listItem = parentListItem;
        }
    }
    if (listItem === null) {
        return false;
    }
    const topListNode = $getTopListNode(listItem);
    const parent = listItem.getParent();
    if (!$isListNode(parent)) {
        formatDevErrorMessage(`A ListItemNode must have a ListNode for a parent.`);
    }
    const grandparent = parent.getParent();
    let replacementNode;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(grandparent)) {
        replacementNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
        topListNode.insertAfter(replacementNode);
    } else if ($isListItemNode(grandparent)) {
        replacementNode = $createListItemNode();
        grandparent.insertAfter(replacementNode);
    } else {
        return false;
    }
    replacementNode.setTextStyle(selection.style).setTextFormat(selection.format).select();
    const nextSiblings = listItem.getNextSiblings();
    if (nextSiblings.length > 0) {
        const newStart = restoreNumbering ? $getNewListStart(parent, listItem) : 1;
        const newList = $createListNode(parent.getListType(), newStart);
        if ($isListItemNode(replacementNode)) {
            const newListItem = $createListItemNode();
            newListItem.append(newList);
            replacementNode.insertAfter(newListItem);
        } else {
            replacementNode.insertAfter(newList);
        }
        newList.append(...nextSiblings);
    }
    // Don't leave hanging nested empty lists
    $removeHighestEmptyListParent(listItem);
    return true;
}
function applyMarkerStyles(dom, node, prevNode) {
    const styles = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getStyleObjectFromCSS"])(node.__textStyle);
    for(const k in styles){
        dom.style.setProperty(`--listitem-marker-${k}`, styles[k]);
    }
    if (prevNode) {
        for(const k in (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["getStyleObjectFromCSS"])(prevNode.__textStyle)){
            if (!(k in styles)) {
                dom.style.removeProperty(`--listitem-marker-${k}`);
            }
        }
    }
}
/** @noInheritDoc */ class ListItemNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"] {
    /** @internal */ __value;
    /** @internal */ __checked;
    /** @internal */ $config() {
        return this.config('listitem', {
            $transform: (node)=>{
                if (node.__checked == null) {
                    return;
                }
                const parent = node.getParent();
                if ($isListNode(parent)) {
                    if (parent.getListType() !== 'check' && node.getChecked() != null) {
                        node.setChecked(undefined);
                    }
                }
            },
            extends: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"],
            importDOM: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildImportMap"])({
                li: ()=>({
                        conversion: $convertListItemElement,
                        priority: 0
                    })
            })
        });
    }
    constructor(value = 1, checked = undefined, key){
        super(key);
        this.__value = value === undefined ? 1 : value;
        this.__checked = checked;
    }
    afterCloneFrom(prevNode) {
        super.afterCloneFrom(prevNode);
        this.__value = prevNode.__value;
        this.__checked = prevNode.__checked;
    }
    createDOM(config) {
        const element = document.createElement('li');
        this.updateListItemDOM(null, element, config);
        return element;
    }
    updateListItemDOM(prevNode, dom, config) {
        updateListItemChecked(dom, this, prevNode);
        dom.value = this.__value;
        $setListItemThemeClassNames(dom, config.theme, this);
        const prevStyle = prevNode ? prevNode.__style : '';
        const nextStyle = this.__style;
        if (prevStyle !== nextStyle) {
            if (nextStyle === '') {
                dom.removeAttribute('style');
            } else {
                dom.style.cssText = nextStyle;
            }
        }
        applyMarkerStyles(dom, this, prevNode);
    }
    updateDOM(prevNode, dom, config) {
        // @ts-expect-error - this is always HTMLListItemElement
        const element = dom;
        this.updateListItemDOM(prevNode, element, config);
        return false;
    }
    updateFromJSON(serializedNode) {
        return super.updateFromJSON(serializedNode).setValue(serializedNode.value).setChecked(serializedNode.checked);
    }
    exportDOM(editor) {
        const element = this.createDOM(editor._config);
        const formatType = this.getFormatType();
        if (formatType) {
            element.style.textAlign = formatType;
        }
        const direction = this.getDirection();
        if (direction) {
            element.dir = direction;
        }
        return {
            element
        };
    }
    exportJSON() {
        return {
            ...super.exportJSON(),
            checked: this.getChecked(),
            value: this.getValue()
        };
    }
    append(...nodes) {
        for(let i = 0; i < nodes.length; i++){
            const node = nodes[i];
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && this.canMergeWith(node)) {
                const children = node.getChildren();
                this.append(...children);
                node.remove();
            } else {
                super.append(node);
            }
        }
        return this;
    }
    replace(replaceWithNode, includeChildren) {
        if ($isListItemNode(replaceWithNode)) {
            return super.replace(replaceWithNode);
        }
        this.setIndent(0);
        const list = this.getParentOrThrow();
        if (!$isListNode(list)) {
            return replaceWithNode;
        }
        if (list.__first === this.getKey()) {
            list.insertBefore(replaceWithNode);
        } else if (list.__last === this.getKey()) {
            list.insertAfter(replaceWithNode);
        } else {
            // Split the list
            const newList = $createListNode(list.getListType());
            let nextSibling = this.getNextSibling();
            while(nextSibling){
                const nodeToAppend = nextSibling;
                nextSibling = nextSibling.getNextSibling();
                newList.append(nodeToAppend);
            }
            list.insertAfter(replaceWithNode);
            replaceWithNode.insertAfter(newList);
        }
        if (includeChildren) {
            if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(replaceWithNode)) {
                formatDevErrorMessage(`includeChildren should only be true for ElementNodes`);
            }
            this.getChildren().forEach((child)=>{
                replaceWithNode.append(child);
            });
        }
        this.remove();
        if (list.getChildrenSize() === 0) {
            list.remove();
        }
        return replaceWithNode;
    }
    insertAfter(node, restoreSelection = true) {
        const listNode = this.getParentOrThrow();
        if (!$isListNode(listNode)) {
            {
                formatDevErrorMessage(`insertAfter: list node is not parent of list item node`);
            }
        }
        if ($isListItemNode(node)) {
            return super.insertAfter(node, restoreSelection);
        }
        const siblings = this.getNextSiblings();
        // Split the lists and insert the node in between them
        listNode.insertAfter(node, restoreSelection);
        if (siblings.length !== 0) {
            const newListNode = $createListNode(listNode.getListType());
            siblings.forEach((sibling)=>newListNode.append(sibling));
            node.insertAfter(newListNode, restoreSelection);
        }
        return node;
    }
    remove(preserveEmptyParent) {
        const prevSibling = this.getPreviousSibling();
        const nextSibling = this.getNextSibling();
        super.remove(preserveEmptyParent);
        if (prevSibling && nextSibling && isNestedListNode(prevSibling) && isNestedListNode(nextSibling)) {
            mergeLists(prevSibling.getFirstChild(), nextSibling.getFirstChild());
            nextSibling.remove();
        }
    }
    insertNewAfter(_, restoreSelection = true) {
        const newElement = $createListItemNode().updateFromJSON(this.exportJSON()).setChecked(this.getChecked() ? false : undefined);
        this.insertAfter(newElement, restoreSelection);
        return newElement;
    }
    collapseAtStart(selection) {
        const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
        const children = this.getChildren();
        children.forEach((child)=>paragraph.append(child));
        const listNode = this.getParentOrThrow();
        const listNodeParent = listNode.getParentOrThrow();
        const isIndented = $isListItemNode(listNodeParent);
        if (listNode.getChildrenSize() === 1) {
            if (isIndented) {
                // if the list node is nested, we just want to remove it,
                // effectively unindenting it.
                listNode.remove();
                listNodeParent.select();
            } else {
                listNode.insertBefore(paragraph);
                listNode.remove();
                // If we have selection on the list item, we'll need to move it
                // to the paragraph
                const anchor = selection.anchor;
                const focus = selection.focus;
                const key = paragraph.getKey();
                if (anchor.type === 'element' && anchor.getNode().is(this)) {
                    anchor.set(key, anchor.offset, 'element');
                }
                if (focus.type === 'element' && focus.getNode().is(this)) {
                    focus.set(key, focus.offset, 'element');
                }
            }
        } else {
            listNode.insertBefore(paragraph);
            this.remove();
        }
        return true;
    }
    getValue() {
        const self = this.getLatest();
        return self.__value;
    }
    setValue(value) {
        const self = this.getWritable();
        self.__value = value;
        return self;
    }
    getChecked() {
        const self = this.getLatest();
        let listType;
        const parent = this.getParent();
        if ($isListNode(parent)) {
            listType = parent.getListType();
        }
        return listType === 'check' ? Boolean(self.__checked) : undefined;
    }
    setChecked(checked) {
        const self = this.getWritable();
        self.__checked = checked;
        return self;
    }
    toggleChecked() {
        const self = this.getWritable();
        return self.setChecked(!self.__checked);
    }
    getIndent() {
        // If we don't have a parent, we are likely serializing
        const parent = this.getParent();
        if (parent === null || !this.isAttached()) {
            return this.getLatest().__indent;
        }
        // ListItemNode should always have a ListNode for a parent.
        let listNodeParent = parent.getParentOrThrow();
        let indentLevel = 0;
        while($isListItemNode(listNodeParent)){
            listNodeParent = listNodeParent.getParentOrThrow().getParentOrThrow();
            indentLevel++;
        }
        return indentLevel;
    }
    setIndent(indent) {
        if (!(typeof indent === 'number')) {
            formatDevErrorMessage(`Invalid indent value.`);
        }
        indent = Math.floor(indent);
        if (!(indent >= 0)) {
            formatDevErrorMessage(`Indent value must be non-negative.`);
        }
        let currentIndent = this.getIndent();
        while(currentIndent !== indent){
            if (currentIndent < indent) {
                $handleIndent(this);
                currentIndent++;
            } else {
                $handleOutdent(this);
                currentIndent--;
            }
        }
        return this;
    }
    /** @deprecated @internal */ canInsertAfter(node) {
        return $isListItemNode(node);
    }
    /** @deprecated @internal */ canReplaceWith(replacement) {
        return $isListItemNode(replacement);
    }
    canMergeWith(node) {
        return $isListItemNode(node) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isParagraphNode"])(node);
    }
    extractWithChild(child, selection) {
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        const anchorNode = selection.anchor.getNode();
        const focusNode = selection.focus.getNode();
        return this.isParentOf(anchorNode) && this.isParentOf(focusNode) && this.getTextContent().length === selection.getTextContent().length;
    }
    isParentRequired() {
        return true;
    }
    createParentElementNode() {
        return $createListNode('bullet');
    }
    canMergeWhenEmpty() {
        return true;
    }
}
function $setListItemThemeClassNames(dom, editorThemeClasses, node) {
    const classesToAdd = [];
    const classesToRemove = [];
    const listTheme = editorThemeClasses.list;
    const listItemClassName = listTheme ? listTheme.listitem : undefined;
    let nestedListItemClassName;
    if (listTheme && listTheme.nested) {
        nestedListItemClassName = listTheme.nested.listitem;
    }
    if (listItemClassName !== undefined) {
        classesToAdd.push(...(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["normalizeClassNames"])(listItemClassName));
    }
    if (listTheme) {
        const parentNode = node.getParent();
        const isCheckList = $isListNode(parentNode) && parentNode.getListType() === 'check';
        const checked = node.getChecked();
        if (!isCheckList || checked) {
            classesToRemove.push(listTheme.listitemUnchecked);
        }
        if (!isCheckList || !checked) {
            classesToRemove.push(listTheme.listitemChecked);
        }
        if (isCheckList) {
            classesToAdd.push(checked ? listTheme.listitemChecked : listTheme.listitemUnchecked);
        }
    }
    if (nestedListItemClassName !== undefined) {
        const nestedListItemClasses = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["normalizeClassNames"])(nestedListItemClassName);
        if (node.getChildren().some((child)=>$isListNode(child))) {
            classesToAdd.push(...nestedListItemClasses);
        } else {
            classesToRemove.push(...nestedListItemClasses);
        }
    }
    if (classesToRemove.length > 0) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["removeClassNamesFromElement"])(dom, ...classesToRemove);
    }
    if (classesToAdd.length > 0) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(dom, ...classesToAdd);
    }
}
function updateListItemChecked(dom, listItemNode, prevListItemNode) {
    const parent = listItemNode.getParent();
    const isCheckbox = $isListNode(parent) && parent.getListType() === 'check' && // Only add attributes for leaf list items
    !$isListNode(listItemNode.getFirstChild());
    if (!isCheckbox) {
        dom.removeAttribute('role');
        dom.removeAttribute('tabIndex');
        dom.removeAttribute('aria-checked');
    } else {
        dom.setAttribute('role', 'checkbox');
        dom.setAttribute('tabIndex', '-1');
        if (!prevListItemNode || listItemNode.__checked !== prevListItemNode.__checked) {
            dom.setAttribute('aria-checked', listItemNode.getChecked() ? 'true' : 'false');
        }
    }
}
function $convertListItemElement(domNode) {
    const isGitHubCheckList = domNode.classList.contains('task-list-item');
    if (isGitHubCheckList) {
        for (const child of domNode.children){
            if (child.tagName === 'INPUT') {
                return $convertCheckboxInput(child);
            }
        }
    }
    const isJoplinCheckList = domNode.classList.contains('joplin-checkbox');
    if (isJoplinCheckList) {
        for (const child of domNode.children){
            if (child.classList.contains('checkbox-wrapper') && child.children.length > 0 && child.children[0].tagName === 'INPUT') {
                return $convertCheckboxInput(child.children[0]);
            }
        }
    }
    const ariaCheckedAttr = domNode.getAttribute('aria-checked');
    const checked = ariaCheckedAttr === 'true' ? true : ariaCheckedAttr === 'false' ? false : undefined;
    return {
        node: $createListItemNode(checked)
    };
}
function $convertCheckboxInput(domNode) {
    const isCheckboxInput = domNode.getAttribute('type') === 'checkbox';
    if (!isCheckboxInput) {
        return {
            node: null
        };
    }
    const checked = domNode.hasAttribute('checked');
    return {
        node: $createListItemNode(checked)
    };
}
/**
 * Creates a new List Item node, passing true/false will convert it to a checkbox input.
 * @param checked - Is the List Item a checkbox and, if so, is it checked? undefined/null: not a checkbox, true/false is a checkbox and checked/unchecked, respectively.
 * @returns The new List Item.
 */ function $createListItemNode(checked) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$applyNodeReplacement"])(new ListItemNode(undefined, checked));
}
/**
 * Checks to see if the node is a ListItemNode.
 * @param node - The node to be checked.
 * @returns true if the node is a ListItemNode, false otherwise.
 */ function $isListItemNode(node) {
    return node instanceof ListItemNode;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /** @noInheritDoc */ class ListNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"] {
    /** @internal */ __tag;
    /** @internal */ __start;
    /** @internal */ __listType;
    /** @internal */ $config() {
        return this.config('list', {
            $transform: (node)=>{
                mergeNextSiblingListIfSameType(node);
                updateChildrenListItemValue(node);
            },
            extends: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"],
            importDOM: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["buildImportMap"])({
                ol: ()=>({
                        conversion: $convertListNode,
                        priority: 0
                    }),
                ul: ()=>({
                        conversion: $convertListNode,
                        priority: 0
                    })
            })
        });
    }
    constructor(listType = 'number', start = 1, key){
        super(key);
        const _listType = TAG_TO_LIST_TYPE[listType] || listType;
        this.__listType = _listType;
        this.__tag = _listType === 'number' ? 'ol' : 'ul';
        this.__start = start;
    }
    afterCloneFrom(prevNode) {
        super.afterCloneFrom(prevNode);
        this.__listType = prevNode.__listType;
        this.__tag = prevNode.__tag;
        this.__start = prevNode.__start;
    }
    getTag() {
        return this.getLatest().__tag;
    }
    setListType(type) {
        const writable = this.getWritable();
        writable.__listType = type;
        writable.__tag = type === 'number' ? 'ol' : 'ul';
        return writable;
    }
    getListType() {
        return this.getLatest().__listType;
    }
    getStart() {
        return this.getLatest().__start;
    }
    setStart(start) {
        const self = this.getWritable();
        self.__start = start;
        return self;
    }
    // View
    createDOM(config, _editor) {
        const tag = this.__tag;
        const dom = document.createElement(tag);
        if (this.__start !== 1) {
            dom.setAttribute('start', String(this.__start));
        }
        // @ts-expect-error Internal field.
        dom.__lexicalListType = this.__listType;
        $setListThemeClassNames(dom, config.theme, this);
        return dom;
    }
    updateDOM(prevNode, dom, config) {
        if (prevNode.__tag !== this.__tag || prevNode.__listType !== this.__listType) {
            return true;
        }
        $setListThemeClassNames(dom, config.theme, this);
        if (prevNode.__start !== this.__start) {
            dom.setAttribute('start', String(this.__start));
        }
        return false;
    }
    updateFromJSON(serializedNode) {
        return super.updateFromJSON(serializedNode).setListType(serializedNode.listType).setStart(serializedNode.start);
    }
    exportDOM(editor) {
        const element = this.createDOM(editor._config, editor);
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(element)) {
            if (this.__start !== 1) {
                element.setAttribute('start', String(this.__start));
            }
            if (this.__listType === 'check') {
                element.setAttribute('__lexicalListType', 'check');
            }
        }
        return {
            element
        };
    }
    exportJSON() {
        return {
            ...super.exportJSON(),
            listType: this.getListType(),
            start: this.getStart(),
            tag: this.getTag()
        };
    }
    canBeEmpty() {
        return false;
    }
    canIndent() {
        return false;
    }
    splice(start, deleteCount, nodesToInsert) {
        let listItemNodesToInsert = nodesToInsert;
        for(let i = 0; i < nodesToInsert.length; i++){
            const node = nodesToInsert[i];
            if (!$isListItemNode(node)) {
                if (listItemNodesToInsert === nodesToInsert) {
                    listItemNodesToInsert = [
                        ...nodesToInsert
                    ];
                }
                listItemNodesToInsert[i] = $createListItemNode().append((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && !($isListNode(node) || node.isInline()) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createTextNode"])(node.getTextContent()) : node);
            }
        }
        return super.splice(start, deleteCount, listItemNodesToInsert);
    }
    extractWithChild(child) {
        return $isListItemNode(child);
    }
}
function $setListThemeClassNames(dom, editorThemeClasses, node) {
    const classesToAdd = [];
    const classesToRemove = [];
    const listTheme = editorThemeClasses.list;
    if (listTheme !== undefined) {
        const listLevelsClassNames = listTheme[`${node.__tag}Depth`] || [];
        const listDepth = $getListDepth(node) - 1;
        const normalizedListDepth = listDepth % listLevelsClassNames.length;
        const listLevelClassName = listLevelsClassNames[normalizedListDepth];
        const listClassName = listTheme[node.__tag];
        let nestedListClassName;
        const nestedListTheme = listTheme.nested;
        const checklistClassName = listTheme.checklist;
        if (nestedListTheme !== undefined && nestedListTheme.list) {
            nestedListClassName = nestedListTheme.list;
        }
        if (listClassName !== undefined) {
            classesToAdd.push(listClassName);
        }
        if (checklistClassName !== undefined && node.__listType === 'check') {
            classesToAdd.push(checklistClassName);
        }
        if (listLevelClassName !== undefined) {
            classesToAdd.push(...(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["normalizeClassNames"])(listLevelClassName));
            for(let i = 0; i < listLevelsClassNames.length; i++){
                if (i !== normalizedListDepth) {
                    classesToRemove.push(node.__tag + i);
                }
            }
        }
        if (nestedListClassName !== undefined) {
            const nestedListItemClasses = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["normalizeClassNames"])(nestedListClassName);
            if (listDepth > 1) {
                classesToAdd.push(...nestedListItemClasses);
            } else {
                classesToRemove.push(...nestedListItemClasses);
            }
        }
    }
    if (classesToRemove.length > 0) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["removeClassNamesFromElement"])(dom, ...classesToRemove);
    }
    if (classesToAdd.length > 0) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(dom, ...classesToAdd);
    }
}
/*
 * This function normalizes the children of a ListNode after the conversion from HTML,
 * ensuring that they are all ListItemNodes and contain either a single nested ListNode
 * or some other inline content.
 */ function $normalizeChildren(nodes) {
    const normalizedListItems = [];
    for(let i = 0; i < nodes.length; i++){
        const node = nodes[i];
        if ($isListItemNode(node)) {
            normalizedListItems.push(node);
            const children = node.getChildren();
            if (children.length > 1) {
                children.forEach((child)=>{
                    if ($isListNode(child)) {
                        normalizedListItems.push($wrapInListItem(child));
                    }
                });
            }
        } else {
            normalizedListItems.push($wrapInListItem(node));
        }
    }
    return normalizedListItems;
}
function isDomChecklist(domNode) {
    if (domNode.getAttribute('__lexicallisttype') === 'check' || // is github checklist
    domNode.classList.contains('contains-task-list') || // is joplin checklist
    domNode.getAttribute('data-is-checklist') === '1') {
        return true;
    }
    // if children are checklist items, the node is a checklist ul. Applicable for googledoc checklist pasting.
    for (const child of domNode.childNodes){
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(child) && child.hasAttribute('aria-checked')) {
            return true;
        }
    }
    return false;
}
function $convertListNode(domNode) {
    const nodeName = domNode.nodeName.toLowerCase();
    let node = null;
    if (nodeName === 'ol') {
        // @ts-ignore
        const start = domNode.start;
        node = $createListNode('number', start);
    } else if (nodeName === 'ul') {
        if (isDomChecklist(domNode)) {
            node = $createListNode('check');
        } else {
            node = $createListNode('bullet');
        }
    }
    return {
        after: $normalizeChildren,
        node
    };
}
const TAG_TO_LIST_TYPE = {
    ol: 'number',
    ul: 'bullet'
};
/**
 * Creates a ListNode of listType.
 * @param listType - The type of list to be created. Can be 'number', 'bullet', or 'check'.
 * @param start - Where an ordered list starts its count, start = 1 if left undefined.
 * @returns The new ListNode
 */ function $createListNode(listType = 'number', start = 1) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$applyNodeReplacement"])(new ListNode(listType, start));
}
/**
 * Checks to see if the node is a ListNode.
 * @param node - The node to be checked.
 * @returns true if the node is a ListNode, false otherwise.
 */ function $isListNode(node) {
    return node instanceof ListNode;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const INSERT_CHECK_LIST_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('INSERT_CHECK_LIST_COMMAND');
/**
 * Registers the checklist plugin with the editor.
 * @param editor The LexicalEditor instance.
 * @param options Optional configuration.
 *   - disableTakeFocusOnClick: If true, clicking a checklist item will not focus the editor (useful for mobile).
 */ function registerCheckList(editor, options) {
    const disableTakeFocusOnClick = options && options.disableTakeFocusOnClick || false;
    const configHandleClick = (event)=>{
        handleClick(event, disableTakeFocusOnClick);
    };
    const configHandleSelectDefaults = (event)=>{
        handleSelectDefaults(event, disableTakeFocusOnClick);
    };
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerCommand(INSERT_CHECK_LIST_COMMAND, ()=>{
        $insertList('check');
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_DOWN_COMMAND"], (event)=>{
        return handleArrowUpOrDown(event, editor, false);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_UP_COMMAND"], (event)=>{
        return handleArrowUpOrDown(event, editor, true);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ESCAPE_COMMAND"], ()=>{
        const activeItem = getActiveCheckListItem();
        if (activeItem != null) {
            const rootElement = editor.getRootElement();
            if (rootElement != null) {
                rootElement.focus();
            }
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_SPACE_COMMAND"], (event)=>{
        const activeItem = getActiveCheckListItem();
        if (activeItem != null && editor.isEditable()) {
            editor.update(()=>{
                const listItemNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(activeItem);
                if ($isListItemNode(listItemNode)) {
                    event.preventDefault();
                    listItemNode.toggleChecked();
                }
            });
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_LEFT_COMMAND"], (event)=>{
        return editor.getEditorState().read(()=>{
            const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed()) {
                const { anchor } = selection;
                const isElement = anchor.type === 'element';
                if (isElement || anchor.offset === 0) {
                    const anchorNode = anchor.getNode();
                    const elementNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(anchorNode, (node)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && !node.isInline());
                    if ($isListItemNode(elementNode)) {
                        const parent = elementNode.getParent();
                        if ($isListNode(parent) && parent.getListType() === 'check' && (isElement || elementNode.getFirstDescendant() === anchorNode)) {
                            const domNode = editor.getElementByKey(elementNode.__key);
                            if (domNode != null && document.activeElement !== domNode) {
                                domNode.focus();
                                event.preventDefault();
                                return true;
                            }
                        }
                    }
                }
            }
            return false;
        });
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerRootListener((rootElement, prevElement)=>{
        if (rootElement !== null) {
            rootElement.addEventListener('click', configHandleClick);
            // Use capture so we run before other listeners that might move focus.
            rootElement.addEventListener('pointerdown', configHandleSelectDefaults, {
                capture: true
            });
            // Some browsers / integrations still generate mousedown events; handle them too.
            rootElement.addEventListener('mousedown', configHandleSelectDefaults, {
                capture: true
            });
            // Intercept touchstart to stop the mobile browser from placing the caret
            // and opening the keyboard when tapping the checklist marker.
            rootElement.addEventListener('touchstart', configHandleSelectDefaults, {
                capture: true,
                passive: false
            });
        }
        if (prevElement !== null) {
            prevElement.removeEventListener('click', configHandleClick);
            prevElement.removeEventListener('pointerdown', configHandleSelectDefaults, {
                capture: true
            });
            prevElement.removeEventListener('mousedown', configHandleSelectDefaults, {
                capture: true
            });
            prevElement.removeEventListener('touchstart', configHandleSelectDefaults, {
                capture: true
            });
        }
    }));
}
function handleCheckItemEvent(event, callback) {
    const target = event.target;
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(target)) {
        return;
    }
    // Ignore clicks on LI that have nested lists
    const firstChild = target.firstChild;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(firstChild) && (firstChild.tagName === 'UL' || firstChild.tagName === 'OL')) {
        return;
    }
    const parentNode = target.parentNode;
    // @ts-ignore internal field
    if (!parentNode || parentNode.__lexicalListType !== 'check') {
        return;
    }
    let clientX = null;
    let pointerType = null;
    if ('clientX' in event) {
        clientX = event.clientX;
    } else if ('touches' in event) {
        const touches = event.touches;
        if (touches.length > 0) {
            clientX = touches[0].clientX;
            pointerType = 'touch';
        }
    }
    // If we couldn't resolve a clientX (unexpected input), bail out.
    if (clientX == null) {
        return;
    }
    const rect = target.getBoundingClientRect();
    const zoom = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["calculateZoomLevel"])(target);
    const clientXInPixels = clientX / zoom;
    // Use getComputedStyle if available, otherwise fallback to 0px width
    const beforeStyles = window.getComputedStyle ? window.getComputedStyle(target, '::before') : {
        width: '0px'
    };
    const beforeWidthInPixels = parseFloat(beforeStyles.width);
    // Make click area slightly larger for touch devices to improve accessibility
    // Determine whether this is a touch event; some environments may supply
    // pointerType on PointerEvent while touch events use the `touches` API above.
    const isTouchEvent = pointerType === 'touch' || event.pointerType === 'touch';
    const clickAreaPadding = isTouchEvent ? 32 : 0; // Add 32px padding for touch events
    if (target.dir === 'rtl' ? clientXInPixels < rect.right + clickAreaPadding && clientXInPixels > rect.right - beforeWidthInPixels - clickAreaPadding : clientXInPixels > rect.left - clickAreaPadding && clientXInPixels < rect.left + beforeWidthInPixels + clickAreaPadding) {
        callback();
    }
}
function handleClick(event, disableFocusOnClick) {
    handleCheckItemEvent(event, ()=>{
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(event.target)) {
            const domNode = event.target;
            const editor = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getNearestEditorFromDOMNode"])(domNode);
            if (editor != null && editor.isEditable()) {
                editor.update(()=>{
                    const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(domNode);
                    if ($isListItemNode(node)) {
                        if (disableFocusOnClick) {
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$addUpdateTag"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SKIP_SELECTION_FOCUS_TAG"]);
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$addUpdateTag"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SKIP_DOM_SELECTION_TAG"]);
                        } else {
                            domNode.focus();
                        }
                        node.toggleChecked();
                    }
                });
            }
        }
    });
}
/**
 * Prevents default focus switch behavior
 *
 * @param event might be of type PointerEvent, MouseEvent, or TouchEvent, hence the generic Event type
 *
 */ function handleSelectDefaults(event, disableTakeFocusOnClick) {
    handleCheckItemEvent(event, ()=>{
        // Prevents caret moving when clicking on check mark.
        event.preventDefault();
        if (disableTakeFocusOnClick) {
            event.stopPropagation();
        }
    });
}
function getActiveCheckListItem() {
    const activeElement = document.activeElement;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(activeElement) && activeElement.tagName === 'LI' && activeElement.parentNode != null && // @ts-ignore internal field
    activeElement.parentNode.__lexicalListType === 'check' ? activeElement : null;
}
function findCheckListItemSibling(node, backward) {
    let sibling = backward ? node.getPreviousSibling() : node.getNextSibling();
    let parent = node;
    // Going up in a tree to get non-null sibling
    while(sibling == null && $isListItemNode(parent)){
        // Get li -> parent ul/ol -> parent li
        parent = parent.getParentOrThrow().getParent();
        if (parent != null) {
            sibling = backward ? parent.getPreviousSibling() : parent.getNextSibling();
        }
    }
    // Going down in a tree to get first non-nested list item
    while($isListItemNode(sibling)){
        const firstChild = backward ? sibling.getLastChild() : sibling.getFirstChild();
        if (!$isListNode(firstChild)) {
            return sibling;
        }
        sibling = backward ? firstChild.getLastChild() : firstChild.getFirstChild();
    }
    return null;
}
function handleArrowUpOrDown(event, editor, backward) {
    const activeItem = getActiveCheckListItem();
    if (activeItem != null) {
        editor.update(()=>{
            const listItem = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(activeItem);
            if (!$isListItemNode(listItem)) {
                return;
            }
            const nextListItem = findCheckListItemSibling(listItem, backward);
            if (nextListItem != null) {
                nextListItem.selectStart();
                const dom = editor.getElementByKey(nextListItem.__key);
                if (dom != null) {
                    event.preventDefault();
                    setTimeout(()=>{
                        dom.focus();
                    }, 0);
                }
            }
        });
    }
    return false;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const UPDATE_LIST_START_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('UPDATE_LIST_START_COMMAND');
const INSERT_UNORDERED_LIST_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('INSERT_UNORDERED_LIST_COMMAND');
const INSERT_ORDERED_LIST_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('INSERT_ORDERED_LIST_COMMAND');
const REMOVE_LIST_COMMAND = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('REMOVE_LIST_COMMAND');
function registerList(editor, options) {
    const removeListener = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerCommand(INSERT_ORDERED_LIST_COMMAND, ()=>{
        $insertList('number');
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(UPDATE_LIST_START_COMMAND, (payload)=>{
        const { listNodeKey, newStart } = payload;
        const listNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNodeByKey"])(listNodeKey);
        if (!$isListNode(listNode)) {
            return false;
        }
        if (listNode.getListType() === 'number') {
            listNode.setStart(newStart);
            updateChildrenListItemValue(listNode);
        }
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(INSERT_UNORDERED_LIST_COMMAND, ()=>{
        $insertList('bullet');
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(REMOVE_LIST_COMMAND, ()=>{
        $removeList();
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_PARAGRAPH_COMMAND"], ()=>{
        const shouldRestore = options && options.restoreNumbering;
        return $handleListInsertParagraph(!!shouldRestore);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_LOW"]), editor.registerNodeTransform(ListItemNode, (node)=>{
        const firstChild = node.getFirstChild();
        if (firstChild) {
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(firstChild)) {
                const style = firstChild.getStyle();
                const format = firstChild.getFormat();
                if (node.getTextStyle() !== style) {
                    node.setTextStyle(style);
                }
                if (node.getTextFormat() !== format) {
                    node.setTextFormat(format);
                }
            }
        } else {
            // If it's empty, check the selection
            const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && (selection.style !== node.getTextStyle() || selection.format !== node.getTextFormat()) && selection.isCollapsed() && node.is(selection.anchor.getNode())) {
                node.setTextStyle(selection.style).setTextFormat(selection.format);
            }
        }
    }), editor.registerNodeTransform(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["TextNode"], (node)=>{
        const listItemParentNode = node.getParent();
        if ($isListItemNode(listItemParentNode) && node.is(listItemParentNode.getFirstChild())) {
            const style = node.getStyle();
            const format = node.getFormat();
            if (style !== listItemParentNode.getTextStyle() || format !== listItemParentNode.getTextFormat()) {
                listItemParentNode.setTextStyle(style).setTextFormat(format);
            }
        }
    }));
    return removeListener;
}
function registerListStrictIndentTransform(editor) {
    const $formatListIndentStrict = (listItemNode)=>{
        const listNode = listItemNode.getParent();
        if ($isListNode(listItemNode.getFirstChild()) || !$isListNode(listNode)) {
            return;
        }
        const startingListItemNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(listItemNode, (node)=>$isListItemNode(node) && $isListNode(node.getParent()) && $isListItemNode(node.getPreviousSibling()));
        if (startingListItemNode === null && listItemNode.getIndent() > 0) {
            listItemNode.setIndent(0);
        } else if ($isListItemNode(startingListItemNode)) {
            const prevListItemNode = startingListItemNode.getPreviousSibling();
            if ($isListItemNode(prevListItemNode)) {
                const endListItemNode = $findChildrenEndListItemNode(prevListItemNode);
                const endListNode = endListItemNode.getParent();
                if ($isListNode(endListNode)) {
                    const prevDepth = $getListDepth(endListNode);
                    const depth = $getListDepth(listNode);
                    if (prevDepth + 1 < depth) {
                        listItemNode.setIndent(prevDepth);
                    }
                }
            }
        }
    };
    const $processListWithStrictIndent = (listNode)=>{
        const queue = [
            listNode
        ];
        while(queue.length > 0){
            const node = queue.shift();
            if (!$isListNode(node)) {
                continue;
            }
            for (const child of node.getChildren()){
                if ($isListItemNode(child)) {
                    $formatListIndentStrict(child);
                    const firstChild = child.getFirstChild();
                    if ($isListNode(firstChild)) {
                        queue.push(firstChild);
                    }
                }
            }
        }
    };
    return editor.registerNodeTransform(ListNode, $processListWithStrictIndent);
}
function $findChildrenEndListItemNode(listItemNode) {
    let current = listItemNode;
    let firstChild = current.getFirstChild();
    while($isListNode(firstChild)){
        const lastChild = firstChild.getLastChild();
        if ($isListItemNode(lastChild)) {
            current = lastChild;
            firstChild = current.getFirstChild();
        } else {
            break;
        }
    }
    return current;
}
/**
 * @deprecated use {@link $insertList} from an update or command listener.
 *
 * Inserts a new ListNode. If the selection's anchor node is an empty ListItemNode and is a child of
 * the root/shadow root, it will replace the ListItemNode with a ListNode and the old ListItemNode.
 * Otherwise it will replace its parent with a new ListNode and re-insert the ListItemNode and any previous children.
 * If the selection's anchor node is not an empty ListItemNode, it will add a new ListNode or merge an existing ListNode,
 * unless the the node is a leaf node, in which case it will attempt to find a ListNode up the branch and replace it with
 * a new ListNode, or create a new ListNode at the nearest root/shadow root.
 * @param editor - The lexical editor.
 * @param listType - The type of list, "number" | "bullet" | "check".
 */ function insertList(editor, listType) {
    editor.update(()=>$insertList(listType));
}
/**
 * @deprecated use {@link $removeList} from an update or command listener.
 *
 * Searches for the nearest ancestral ListNode and removes it. If selection is an empty ListItemNode
 * it will remove the whole list, including the ListItemNode. For each ListItemNode in the ListNode,
 * removeList will also generate new ParagraphNodes in the removed ListNode's place. Any child node
 * inside a ListItemNode will be appended to the new ParagraphNodes.
 * @param editor - The lexical editor.
 */ function removeList(editor) {
    editor.update(()=>$removeList());
}
/**
 * Configures {@link ListNode}, {@link ListItemNode} and registers
 * the strict indent transform if `hasStrictIndent` is true (default false).
 */ const ListExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    build (editor, config, state) {
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["namedSignals"])(config);
    },
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        hasStrictIndent: false,
        shouldPreserveNumbering: false
    }),
    name: '@lexical/list/List',
    nodes: ()=>[
            ListNode,
            ListItemNode
        ],
    register (editor, config, state) {
        const stores = state.getOutput();
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["effect"])(()=>{
            return registerList(editor, {
                restoreNumbering: stores.shouldPreserveNumbering.value
            });
        }), (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$extension$2f$LexicalExtension$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["effect"])(()=>stores.hasStrictIndent.value ? registerListStrictIndentTransform(editor) : undefined));
    }
});
/**
 * Registers checklist functionality for {@link ListNode} and
 * {@link ListItemNode} with a
 * {@link INSERT_CHECK_LIST_COMMAND} listener and
 * the expected keyboard and mouse interactions for
 * checkboxes.
 */ const CheckListExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    config: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["safeCast"])({
        disableTakeFocusOnClick: false
    }),
    dependencies: [
        ListExtension
    ],
    name: '@lexical/list/CheckList',
    register: registerCheckList
});
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/react/LexicalDecoratorBlockNode.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$isDecoratorBlockNode",
    ()=>$isDecoratorBlockNode,
    "DecoratorBlockNode",
    ()=>DecoratorBlockNode
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ class DecoratorBlockNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DecoratorNode"] {
    __format;
    constructor(format, key){
        super(key);
        this.__format = format || '';
    }
    exportJSON() {
        return {
            ...super.exportJSON(),
            format: this.__format || ''
        };
    }
    updateFromJSON(serializedNode) {
        return super.updateFromJSON(serializedNode).setFormat(serializedNode.format || '');
    }
    canIndent() {
        return false;
    }
    createDOM() {
        return document.createElement('div');
    }
    updateDOM() {
        return false;
    }
    setFormat(format) {
        const self = this.getWritable();
        self.__format = format;
        return self;
    }
    isInline() {
        return false;
    }
}
function $isDecoratorBlockNode(node) {
    return node instanceof DecoratorBlockNode;
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/rich-text/LexicalRichText.dev.mjs [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$createHeadingNode",
    ()=>$createHeadingNode,
    "$createQuoteNode",
    ()=>$createQuoteNode,
    "$isHeadingNode",
    ()=>$isHeadingNode,
    "$isQuoteNode",
    ()=>$isQuoteNode,
    "DRAG_DROP_PASTE",
    ()=>DRAG_DROP_PASTE,
    "HeadingNode",
    ()=>HeadingNode,
    "QuoteNode",
    ()=>QuoteNode,
    "RichTextExtension",
    ()=>RichTextExtension,
    "eventFiles",
    ()=>eventFiles,
    "registerRichText",
    ()=>registerRichText
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$clipboard$2f$LexicalClipboard$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/clipboard/LexicalClipboard.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$dragon$2f$LexicalDragon$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/dragon/LexicalDragon.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/utils/LexicalUtils.dev.mjs [app-rsc] (ecmascript) <locals>");
;
;
;
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function caretFromPoint(x, y) {
    if (typeof document.caretRangeFromPoint !== 'undefined') {
        const range = document.caretRangeFromPoint(x, y);
        if (range === null) {
            return null;
        }
        return {
            node: range.startContainer,
            offset: range.startOffset
        };
    // @ts-ignore
    } else if (document.caretPositionFromPoint !== 'undefined') {
        // @ts-ignore FF - no types
        const range = document.caretPositionFromPoint(x, y);
        if (range === null) {
            return null;
        }
        return {
            node: range.offsetNode,
            offset: range.offset
        };
    } else {
        // Gracefully handle IE
        return null;
    }
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const CAN_USE_DOM = ("TURBOPACK compile-time value", "undefined") !== 'undefined' && typeof window.document !== 'undefined' && typeof window.document.createElement !== 'undefined';
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const documentMode = ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : null;
const IS_APPLE = CAN_USE_DOM && /Mac|iPod|iPhone|iPad/.test(navigator.platform);
const CAN_USE_BEFORE_INPUT = ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : false;
const IS_SAFARI = CAN_USE_DOM && /Version\/[\d.]+.*Safari/.test(navigator.userAgent);
const IS_IOS = CAN_USE_DOM && /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
// Keep these in case we need to use them in the future.
// export const IS_WINDOWS: boolean = CAN_USE_DOM && /Win/.test(navigator.platform);
const IS_CHROME = CAN_USE_DOM && /^(?=.*Chrome).*/i.test(navigator.userAgent);
const IS_APPLE_WEBKIT = CAN_USE_DOM && /AppleWebKit\/[\d.]+/.test(navigator.userAgent) && IS_APPLE && !IS_CHROME;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const DRAG_DROP_PASTE = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["createCommand"])('DRAG_DROP_PASTE_FILE');
/** @noInheritDoc */ class QuoteNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"] {
    static getType() {
        return 'quote';
    }
    static clone(node) {
        return new QuoteNode(node.__key);
    }
    // View
    createDOM(config) {
        const element = document.createElement('blockquote');
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(element, config.theme.quote);
        return element;
    }
    updateDOM(prevNode, dom) {
        return false;
    }
    static importDOM() {
        return {
            blockquote: (node)=>({
                    conversion: $convertBlockquoteElement,
                    priority: 0
                })
        };
    }
    exportDOM(editor) {
        const { element } = super.exportDOM(editor);
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(element)) {
            if (this.isEmpty()) {
                element.append(document.createElement('br'));
            }
            const formatType = this.getFormatType();
            if (formatType) {
                element.style.textAlign = formatType;
            }
            const direction = this.getDirection();
            if (direction) {
                element.dir = direction;
            }
        }
        return {
            element
        };
    }
    static importJSON(serializedNode) {
        return $createQuoteNode().updateFromJSON(serializedNode);
    }
    // Mutation
    insertNewAfter(_, restoreSelection) {
        const newBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
        const direction = this.getDirection();
        newBlock.setDirection(direction);
        this.insertAfter(newBlock, restoreSelection);
        return newBlock;
    }
    collapseAtStart() {
        const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
        const children = this.getChildren();
        children.forEach((child)=>paragraph.append(child));
        this.replace(paragraph);
        return true;
    }
    canMergeWhenEmpty() {
        return true;
    }
}
function $createQuoteNode() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$applyNodeReplacement"])(new QuoteNode());
}
function $isQuoteNode(node) {
    return node instanceof QuoteNode;
}
/** @noInheritDoc */ class HeadingNode extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ElementNode"] {
    /** @internal */ __tag;
    static getType() {
        return 'heading';
    }
    static clone(node) {
        return new HeadingNode(node.__tag, node.__key);
    }
    constructor(tag, key){
        super(key);
        this.__tag = tag;
    }
    getTag() {
        return this.__tag;
    }
    setTag(tag) {
        const self = this.getWritable();
        this.__tag = tag;
        return self;
    }
    // View
    createDOM(config) {
        const tag = this.__tag;
        const element = document.createElement(tag);
        const theme = config.theme;
        const classNames = theme.heading;
        if (classNames !== undefined) {
            const className = classNames[tag];
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addClassNamesToElement"])(element, className);
        }
        return element;
    }
    updateDOM(prevNode, dom, config) {
        return prevNode.__tag !== this.__tag;
    }
    static importDOM() {
        return {
            h1: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            h2: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            h3: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            h4: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            h5: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            h6: (node)=>({
                    conversion: $convertHeadingElement,
                    priority: 0
                }),
            p: (node)=>{
                // domNode is a <p> since we matched it by nodeName
                const paragraph = node;
                const firstChild = paragraph.firstChild;
                if (firstChild !== null && isGoogleDocsTitle(firstChild)) {
                    return {
                        conversion: ()=>({
                                node: null
                            }),
                        priority: 3
                    };
                }
                return null;
            },
            span: (node)=>{
                if (isGoogleDocsTitle(node)) {
                    return {
                        conversion: (domNode)=>{
                            return {
                                node: $createHeadingNode('h1')
                            };
                        },
                        priority: 3
                    };
                }
                return null;
            }
        };
    }
    exportDOM(editor) {
        const { element } = super.exportDOM(editor);
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(element)) {
            if (this.isEmpty()) {
                element.append(document.createElement('br'));
            }
            const formatType = this.getFormatType();
            if (formatType) {
                element.style.textAlign = formatType;
            }
            const direction = this.getDirection();
            if (direction) {
                element.dir = direction;
            }
        }
        return {
            element
        };
    }
    static importJSON(serializedNode) {
        return $createHeadingNode(serializedNode.tag).updateFromJSON(serializedNode);
    }
    updateFromJSON(serializedNode) {
        return super.updateFromJSON(serializedNode).setTag(serializedNode.tag);
    }
    exportJSON() {
        return {
            ...super.exportJSON(),
            tag: this.getTag()
        };
    }
    // Mutation
    insertNewAfter(selection, restoreSelection = true) {
        const anchorOffet = selection ? selection.anchor.offset : 0;
        const lastDesc = this.getLastDescendant();
        const isAtEnd = !lastDesc || selection && selection.anchor.key === lastDesc.getKey() && anchorOffet === lastDesc.getTextContentSize();
        const newElement = isAtEnd || !selection ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])() : $createHeadingNode(this.getTag());
        const direction = this.getDirection();
        newElement.setDirection(direction);
        this.insertAfter(newElement, restoreSelection);
        if (anchorOffet === 0 && !this.isEmpty() && selection) {
            const paragraph = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
            paragraph.select();
            this.replace(paragraph, true);
        }
        return newElement;
    }
    collapseAtStart() {
        const newElement = !this.isEmpty() ? $createHeadingNode(this.getTag()) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])();
        const children = this.getChildren();
        children.forEach((child)=>newElement.append(child));
        this.replace(newElement);
        return true;
    }
    extractWithChild() {
        return true;
    }
}
function isGoogleDocsTitle(domNode) {
    if (domNode.nodeName.toLowerCase() === 'span') {
        return domNode.style.fontSize === '26pt';
    }
    return false;
}
function $convertHeadingElement(element) {
    const nodeName = element.nodeName.toLowerCase();
    let node = null;
    if (nodeName === 'h1' || nodeName === 'h2' || nodeName === 'h3' || nodeName === 'h4' || nodeName === 'h5' || nodeName === 'h6') {
        node = $createHeadingNode(nodeName);
        if (element.style !== null) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["setNodeIndentFromDOM"])(element, node);
            node.setFormat(element.style.textAlign);
        }
    }
    return {
        node
    };
}
function $convertBlockquoteElement(element) {
    const node = $createQuoteNode();
    if (element.style !== null) {
        node.setFormat(element.style.textAlign);
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["setNodeIndentFromDOM"])(element, node);
    }
    return {
        node
    };
}
function $createHeadingNode(headingTag = 'h1') {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$applyNodeReplacement"])(new HeadingNode(headingTag));
}
function $isHeadingNode(node) {
    return node instanceof HeadingNode;
}
function onPasteForRichText(event, editor) {
    event.preventDefault();
    editor.update(()=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        const clipboardData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, InputEvent) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, KeyboardEvent) ? null : event.clipboardData;
        if (clipboardData != null && selection !== null) {
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$clipboard$2f$LexicalClipboard$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$insertDataTransferForRichText"])(clipboardData, selection, editor);
        }
    }, {
        tag: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PASTE_TAG"]
    });
}
async function onCutForRichText(event, editor) {
    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$clipboard$2f$LexicalClipboard$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["copyToClipboard"])(editor, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, ClipboardEvent) ? event : null);
    editor.update(()=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            selection.removeText();
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            selection.getNodes().forEach((node)=>node.remove());
        }
    });
}
// Clipboard may contain files that we aren't allowed to read. While the event is arguably useless,
// in certain occasions, we want to know whether it was a file transfer, as opposed to text. We
// control this with the first boolean flag.
function eventFiles(event) {
    let dataTransfer = null;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, DragEvent)) {
        dataTransfer = event.dataTransfer;
    } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, ClipboardEvent)) {
        dataTransfer = event.clipboardData;
    }
    if (dataTransfer === null) {
        return [
            false,
            [],
            false
        ];
    }
    const types = dataTransfer.types;
    const hasFiles = types.includes('Files');
    const hasContent = types.includes('text/html') || types.includes('text/plain');
    return [
        hasFiles,
        Array.from(dataTransfer.files),
        hasContent
    ];
}
function $isTargetWithinDecorator(target) {
    const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(target);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isDecoratorNode"])(node);
}
function $isSelectionAtEndOfRoot(selection) {
    const focus = selection.focus;
    return focus.key === 'root' && focus.offset === (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])().getChildrenSize();
}
function $isSelectionCollapsedAtFrontOfIndentedBlock(selection) {
    if (!selection.isCollapsed()) {
        return false;
    }
    const { anchor } = selection;
    if (anchor.offset !== 0) {
        return false;
    }
    const anchorNode = anchor.getNode();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootNode"])(anchorNode)) {
        return false;
    }
    const element = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$getNearestBlockElementAncestorOrThrow"])(anchorNode);
    return element.getIndent() > 0 && (element.is(anchorNode) || anchorNode.is(element.getFirstDescendant()));
}
/**
 * Resets the capitalization of the selection to default.
 * Called when the user presses space, tab, or enter key.
 * @param selection The selection to reset the capitalization of.
 */ function $resetCapitalization(selection) {
    for (const format of [
        'lowercase',
        'uppercase',
        'capitalize'
    ]){
        if (selection.hasFormat(format)) {
            selection.toggleFormat(format);
        }
    }
}
function registerRichText(editor) {
    const removeListener = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CLICK_COMMAND"], (payload)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            selection.clear();
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DELETE_CHARACTER_COMMAND"], (isBackward)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            selection.deleteCharacter(isBackward);
            return true;
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            selection.deleteNodes();
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DELETE_WORD_COMMAND"], (isBackward)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.deleteWord(isBackward);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DELETE_LINE_COMMAND"], (isBackward)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.deleteLine(isBackward);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CONTROLLED_TEXT_INSERTION_COMMAND"], (eventOrText)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (typeof eventOrText === 'string') {
            if (selection !== null) {
                selection.insertText(eventOrText);
            }
        } else {
            if (selection === null) {
                return false;
            }
            const dataTransfer = eventOrText.dataTransfer;
            if (dataTransfer != null) {
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$clipboard$2f$LexicalClipboard$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$insertDataTransferForRichText"])(dataTransfer, selection, editor);
            } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
                const data = eventOrText.data;
                if (data) {
                    selection.insertText(data);
                }
                return true;
            }
        }
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["REMOVE_TEXT_COMMAND"], ()=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.removeText();
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["FORMAT_TEXT_COMMAND"], (format)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.formatText(format);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["FORMAT_ELEMENT_COMMAND"], (format)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            return false;
        }
        const nodes = selection.getNodes();
        for (const node of nodes){
            const element = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(node, (parentNode)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(parentNode) && !parentNode.isInline());
            if (element !== null) {
                element.setFormat(format);
            }
        }
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_LINE_BREAK_COMMAND"], (selectStart)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.insertLineBreak(selectStart);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_PARAGRAPH_COMMAND"], ()=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        selection.insertParagraph();
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_TAB_COMMAND"], ()=>{
        const tabNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createTabNode"])();
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            tabNode.setFormat(selection.format);
            tabNode.setStyle(selection.style);
        }
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$insertNodes"])([
            tabNode
        ]);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INDENT_CONTENT_COMMAND"], ()=>{
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$handleIndentAndOutdent"])((block)=>{
            const indent = block.getIndent();
            block.setIndent(indent + 1);
        });
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["OUTDENT_CONTENT_COMMAND"], ()=>{
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$handleIndentAndOutdent"])((block)=>{
            const indent = block.getIndent();
            if (indent > 0) {
                block.setIndent(Math.max(0, indent - 1));
            }
        });
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_UP_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            // If selection is on a node, let's try and move selection
            // back to being a range selection.
            const nodes = selection.getNodes();
            if (nodes.length > 0) {
                event.preventDefault();
                nodes[0].selectPrevious();
                return true;
            }
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            const possibleNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentNode"])(selection.focus, true);
            if (!event.shiftKey && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isDecoratorNode"])(possibleNode) && !possibleNode.isIsolated() && !possibleNode.isInline()) {
                possibleNode.selectPrevious();
                event.preventDefault();
                return true;
            }
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_DOWN_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            // If selection is on a node, let's try and move selection
            // back to being a range selection.
            const nodes = selection.getNodes();
            if (nodes.length > 0) {
                event.preventDefault();
                nodes[0].selectNext(0, 0);
                return true;
            }
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            if ($isSelectionAtEndOfRoot(selection)) {
                event.preventDefault();
                return true;
            }
            const possibleNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentNode"])(selection.focus, false);
            if (!event.shiftKey && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isDecoratorNode"])(possibleNode) && !possibleNode.isIsolated() && !possibleNode.isInline()) {
                possibleNode.selectNext();
                event.preventDefault();
                return true;
            }
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_LEFT_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            // If selection is on a node, let's try and move selection
            // back to being a range selection.
            const nodes = selection.getNodes();
            if (nodes.length > 0) {
                event.preventDefault();
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$isParentRTL"])(nodes[0])) {
                    nodes[0].selectNext(0, 0);
                } else {
                    nodes[0].selectPrevious();
                }
                return true;
            }
        }
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$shouldOverrideDefaultCharacterSelection"])(selection, true)) {
            const isHoldingShift = event.shiftKey;
            event.preventDefault();
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$moveCharacter"])(selection, isHoldingShift, true);
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ARROW_RIGHT_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            // If selection is on a node, let's try and move selection
            // back to being a range selection.
            const nodes = selection.getNodes();
            if (nodes.length > 0) {
                event.preventDefault();
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$isParentRTL"])(nodes[0])) {
                    nodes[0].selectPrevious();
                } else {
                    nodes[0].selectNext(0, 0);
                }
                return true;
            }
        }
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        const isHoldingShift = event.shiftKey;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$shouldOverrideDefaultCharacterSelection"])(selection, false)) {
            event.preventDefault();
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["$moveCharacter"])(selection, isHoldingShift, false);
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_BACKSPACE_COMMAND"], (event)=>{
        if ($isTargetWithinDecorator(event.target)) {
            return false;
        }
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            if ($isSelectionCollapsedAtFrontOfIndentedBlock(selection)) {
                event.preventDefault();
                return editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["OUTDENT_CONTENT_COMMAND"], undefined);
            }
            // Exception handling for iOS native behavior instead of Lexical's behavior when using Korean on iOS devices.
            // more details - https://github.com/facebook/lexical/issues/5841
            if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
            ;
        } else if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection)) {
            return false;
        }
        event.preventDefault();
        return editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DELETE_CHARACTER_COMMAND"], true);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_DELETE_COMMAND"], (event)=>{
        if ($isTargetWithinDecorator(event.target)) {
            return false;
        }
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isNodeSelection"])(selection))) {
            return false;
        }
        event.preventDefault();
        return editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DELETE_CHARACTER_COMMAND"], false);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ENTER_COMMAND"], (event)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        $resetCapitalization(selection);
        if (event !== null) {
            // If we have beforeinput, then we can avoid blocking
            // the default behavior. This ensures that the iOS can
            // intercept that we're actually inserting a paragraph,
            // and autocomplete, autocapitalize etc work as intended.
            // This can also cause a strange performance issue in
            // Safari, where there is a noticeable pause due to
            // preventing the key down of enter.
            if ("TURBOPACK compile-time falsy", 0) //TURBOPACK unreachable
            ;
            event.preventDefault();
            if (event.shiftKey) {
                return editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_LINE_BREAK_COMMAND"], false);
            }
        }
        return editor.dispatchCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INSERT_PARAGRAPH_COMMAND"], undefined);
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_ESCAPE_COMMAND"], ()=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        editor.blur();
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DROP_COMMAND"], (event)=>{
        const [, files] = eventFiles(event);
        if (files.length > 0) {
            const x = event.clientX;
            const y = event.clientY;
            const eventRange = caretFromPoint(x, y);
            if (eventRange !== null) {
                const { offset: domOffset, node: domNode } = eventRange;
                const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(domNode);
                if (node !== null) {
                    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createRangeSelection"])();
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(node)) {
                        selection.anchor.set(node.getKey(), domOffset, 'text');
                        selection.focus.set(node.getKey(), domOffset, 'text');
                    } else {
                        const parentKey = node.getParentOrThrow().getKey();
                        const offset = node.getIndexWithinParent() + 1;
                        selection.anchor.set(parentKey, offset, 'element');
                        selection.focus.set(parentKey, offset, 'element');
                    }
                    const normalizedSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$normalizeSelection__EXPERIMENTAL"])(selection);
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelection"])(normalizedSelection);
                }
                editor.dispatchCommand(DRAG_DROP_PASTE, files);
            }
            event.preventDefault();
            return true;
        }
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DRAGSTART_COMMAND"], (event)=>{
        const [isFileTransfer] = eventFiles(event);
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (isFileTransfer && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DRAGOVER_COMMAND"], (event)=>{
        const [isFileTransfer] = eventFiles(event);
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (isFileTransfer && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            return false;
        }
        const x = event.clientX;
        const y = event.clientY;
        const eventRange = caretFromPoint(x, y);
        if (eventRange !== null) {
            const node = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNearestNodeFromDOMNode"])(eventRange.node);
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isDecoratorNode"])(node)) {
                // Show browser caret as the user is dragging the media across the screen. Won't work
                // for DecoratorNode nor it's relevant.
                event.preventDefault();
            }
        }
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["SELECT_ALL_COMMAND"], ()=>{
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$selectAll"])();
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COPY_COMMAND"], (event)=>{
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$clipboard$2f$LexicalClipboard$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["copyToClipboard"])(editor, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$utils$2f$LexicalUtils$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["objectKlassEquals"])(event, ClipboardEvent) ? event : null);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["CUT_COMMAND"], (event)=>{
        onCutForRichText(event, editor);
        return true;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PASTE_COMMAND"], (event)=>{
        const [, files, hasTextContent] = eventFiles(event);
        if (files.length > 0 && !hasTextContent) {
            editor.dispatchCommand(DRAG_DROP_PASTE, files);
            return true;
        }
        // if inputs then paste within the input ignore creating a new node on paste event
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isDOMNode"])(event.target) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isSelectionCapturedInDecoratorInput"])(event.target)) {
            return false;
        }
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if (selection !== null) {
            onPasteForRichText(event, editor);
            return true;
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_SPACE_COMMAND"], (_)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            $resetCapitalization(selection);
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]), editor.registerCommand(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["KEY_TAB_COMMAND"], (_)=>{
        const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
            $resetCapitalization(selection);
        }
        return false;
    }, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["COMMAND_PRIORITY_EDITOR"]));
    return removeListener;
}
/**
 * An extension to register \@lexical/rich-text behavior and nodes
 * ({@link HeadingNode}, {@link QuoteNode})
 */ const RichTextExtension = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defineExtension"])({
    conflictsWith: [
        '@lexical/plain-text'
    ],
    dependencies: [
        __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$dragon$2f$LexicalDragon$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["DragonExtension"]
    ],
    name: '@lexical/rich-text',
    nodes: ()=>[
            HeadingNode,
            QuoteNode
        ],
    register: registerRichText
});
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$addNodeStyle",
    ()=>$addNodeStyle,
    "$copyBlockFormatIndent",
    ()=>$copyBlockFormatIndent,
    "$ensureForwardRangeSelection",
    ()=>$ensureForwardRangeSelection,
    "$forEachSelectedTextNode",
    ()=>$forEachSelectedTextNode,
    "$getComputedStyleForElement",
    ()=>$getComputedStyleForElement,
    "$getComputedStyleForParent",
    ()=>$getComputedStyleForParent,
    "$getSelectionStyleValueForProperty",
    ()=>$getSelectionStyleValueForProperty,
    "$isAtNodeEnd",
    ()=>$isAtNodeEnd,
    "$isParentElementRTL",
    ()=>$isParentElementRTL,
    "$isParentRTL",
    ()=>$isParentRTL,
    "$moveCaretSelection",
    ()=>$moveCaretSelection,
    "$moveCharacter",
    ()=>$moveCharacter,
    "$patchStyleText",
    ()=>$patchStyleText,
    "$setBlocksType",
    ()=>$setBlocksType,
    "$shouldOverrideDefaultCharacterSelection",
    ()=>$shouldOverrideDefaultCharacterSelection,
    "$sliceSelectedTextNodeContent",
    ()=>$sliceSelectedTextNodeContent,
    "$trimTextContentFromAnchor",
    ()=>$trimTextContentFromAnchor,
    "$wrapNodes",
    ()=>$wrapNodes,
    "createDOMRange",
    ()=>createDOMRange,
    "createRectsFromDOMRange",
    ()=>createRectsFromDOMRange,
    "getCSSFromStyleObject",
    ()=>getCSSFromStyleObject,
    "getStyleObjectFromCSS",
    ()=>getStyleObjectFromCSS,
    "trimTextContentFromAnchor",
    ()=>trimTextContentFromAnchor
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ // Do not require this module directly! Use normal `invariant` calls.
function formatDevErrorMessage(message) {
    throw new Error(message);
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const CSS_TO_STYLES = new Map();
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function getDOMTextNode(element) {
    let node = element;
    while(node != null){
        if (node.nodeType === Node.TEXT_NODE) {
            return node;
        }
        node = node.firstChild;
    }
    return null;
}
function getDOMIndexWithinParent(node) {
    const parent = node.parentNode;
    if (parent == null) {
        throw new Error('Should never happen');
    }
    return [
        parent,
        Array.from(parent.childNodes).indexOf(node)
    ];
}
/**
 * Creates a selection range for the DOM.
 * @param editor - The lexical editor.
 * @param anchorNode - The anchor node of a selection.
 * @param _anchorOffset - The amount of space offset from the anchor to the focus.
 * @param focusNode - The current focus.
 * @param _focusOffset - The amount of space offset from the focus to the anchor.
 * @returns The range of selection for the DOM that was created.
 */ function createDOMRange(editor, anchorNode, _anchorOffset, focusNode, _focusOffset) {
    const anchorKey = anchorNode.getKey();
    const focusKey = focusNode.getKey();
    const range = document.createRange();
    let anchorDOM = editor.getElementByKey(anchorKey);
    let focusDOM = editor.getElementByKey(focusKey);
    let anchorOffset = _anchorOffset;
    let focusOffset = _focusOffset;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(anchorNode)) {
        anchorDOM = getDOMTextNode(anchorDOM);
    }
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(focusNode)) {
        focusDOM = getDOMTextNode(focusDOM);
    }
    if (anchorNode === undefined || focusNode === undefined || anchorDOM === null || focusDOM === null) {
        return null;
    }
    if (anchorDOM.nodeName === 'BR') {
        [anchorDOM, anchorOffset] = getDOMIndexWithinParent(anchorDOM);
    }
    if (focusDOM.nodeName === 'BR') {
        [focusDOM, focusOffset] = getDOMIndexWithinParent(focusDOM);
    }
    const firstChild = anchorDOM.firstChild;
    if (anchorDOM === focusDOM && firstChild != null && firstChild.nodeName === 'BR' && anchorOffset === 0 && focusOffset === 0) {
        focusOffset = 1;
    }
    try {
        range.setStart(anchorDOM, anchorOffset);
        range.setEnd(focusDOM, focusOffset);
    } catch (_e) {
        return null;
    }
    if (range.collapsed && (anchorOffset !== focusOffset || anchorKey !== focusKey)) {
        // Range is backwards, we need to reverse it
        range.setStart(focusDOM, focusOffset);
        range.setEnd(anchorDOM, anchorOffset);
    }
    return range;
}
/**
 * Creates DOMRects, generally used to help the editor find a specific location on the screen.
 * @param editor - The lexical editor
 * @param range - A fragment of a document that can contain nodes and parts of text nodes.
 * @returns The selectionRects as an array.
 */ function createRectsFromDOMRange(editor, range) {
    const rootElement = editor.getRootElement();
    if (rootElement === null) {
        return [];
    }
    const rootRect = rootElement.getBoundingClientRect();
    const computedStyle = getComputedStyle(rootElement);
    const rootPadding = parseFloat(computedStyle.paddingLeft) + parseFloat(computedStyle.paddingRight);
    const selectionRects = Array.from(range.getClientRects());
    let selectionRectsLength = selectionRects.length;
    //sort rects from top left to bottom right.
    selectionRects.sort((a, b)=>{
        const top = a.top - b.top;
        // Some rects match position closely, but not perfectly,
        // so we give a 3px tolerance.
        if (Math.abs(top) <= 3) {
            return a.left - b.left;
        }
        return top;
    });
    let prevRect;
    for(let i = 0; i < selectionRectsLength; i++){
        const selectionRect = selectionRects[i];
        // Exclude rects that overlap preceding Rects in the sorted list.
        const isOverlappingRect = prevRect && prevRect.top <= selectionRect.top && prevRect.top + prevRect.height > selectionRect.top && prevRect.left + prevRect.width > selectionRect.left;
        // Exclude selections that span the entire element
        const selectionSpansElement = selectionRect.width + rootPadding === rootRect.width;
        if (isOverlappingRect || selectionSpansElement) {
            selectionRects.splice(i--, 1);
            selectionRectsLength--;
            continue;
        }
        prevRect = selectionRect;
    }
    return selectionRects;
}
/**
 * Creates an object containing all the styles and their values provided in the CSS string.
 * @param css - The CSS string of styles and their values.
 * @returns The styleObject containing all the styles and their values.
 */ function getStyleObjectFromRawCSS(css) {
    const styleObject = {};
    if (!css) {
        return styleObject;
    }
    const styles = css.split(';');
    for (const style of styles){
        if (style !== '') {
            const [key, value] = style.split(/:([^]+)/); // split on first colon
            if (key && value) {
                styleObject[key.trim()] = value.trim();
            }
        }
    }
    return styleObject;
}
/**
 * Given a CSS string, returns an object from the style cache.
 * @param css - The CSS property as a string.
 * @returns The value of the given CSS property.
 */ function getStyleObjectFromCSS(css) {
    let value = CSS_TO_STYLES.get(css);
    if (value === undefined) {
        value = getStyleObjectFromRawCSS(css);
        CSS_TO_STYLES.set(css, value);
    }
    {
        // Freeze the value in DEV to prevent accidental mutations
        Object.freeze(value);
    }
    return value;
}
/**
 * Gets the CSS styles from the style object.
 * @param styles - The style object containing the styles to get.
 * @returns A string containing the CSS styles and their values.
 */ function getCSSFromStyleObject(styles) {
    let css = '';
    for(const style in styles){
        if (style) {
            css += `${style}: ${styles[style]};`;
        }
    }
    return css;
}
/**
 * Gets the computed DOM styles of the element.
 * @param element - The node to check the styles for.
 * @returns the computed styles of the element or null if there is no DOM element or no default view for the document.
 */ function $getComputedStyleForElement(element) {
    const editor = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getEditor"])();
    const domElement = editor.getElementByKey(element.getKey());
    if (domElement === null) {
        return null;
    }
    const view = domElement.ownerDocument.defaultView;
    if (view === null) {
        return null;
    }
    return view.getComputedStyle(domElement);
}
/**
 * Gets the computed DOM styles of the parent of the node.
 * @param node - The node to check its parent's styles for.
 * @returns the computed styles of the node or null if there is no DOM element or no default view for the document.
 */ function $getComputedStyleForParent(node) {
    const parent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootNode"])(node) ? node : node.getParentOrThrow();
    return $getComputedStyleForElement(parent);
}
/**
 * Determines whether a node's parent is RTL.
 * @param node - The node to check whether it is RTL.
 * @returns whether the node is RTL.
 */ function $isParentRTL(node) {
    const styles = $getComputedStyleForParent(node);
    return styles !== null && styles.direction === 'rtl';
}
/**
 * Generally used to append text content to HTML and JSON. Grabs the text content and "slices"
 * it to be generated into the new TextNode.
 * @param selection - The selection containing the node whose TextNode is to be edited.
 * @param textNode - The TextNode to be edited.
 * @param mutates - 'clone' to return a clone before mutating, 'self' to update in-place
 * @returns The updated TextNode or clone.
 */ function $sliceSelectedTextNodeContent(selection, textNode, mutates = 'self') {
    const anchorAndFocus = selection.getStartEndPoints();
    if (textNode.isSelected(selection) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTokenOrSegmented"])(textNode) && anchorAndFocus !== null) {
        const [anchor, focus] = anchorAndFocus;
        const isBackward = selection.isBackward();
        const anchorNode = anchor.getNode();
        const focusNode = focus.getNode();
        const isAnchor = textNode.is(anchorNode);
        const isFocus = textNode.is(focusNode);
        if (isAnchor || isFocus) {
            const [anchorOffset, focusOffset] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getCharacterOffsets"])(selection);
            const isSame = anchorNode.is(focusNode);
            const isFirst = textNode.is(isBackward ? focusNode : anchorNode);
            const isLast = textNode.is(isBackward ? anchorNode : focusNode);
            let startOffset = 0;
            let endOffset = undefined;
            if (isSame) {
                startOffset = anchorOffset > focusOffset ? focusOffset : anchorOffset;
                endOffset = anchorOffset > focusOffset ? anchorOffset : focusOffset;
            } else if (isFirst) {
                const offset = isBackward ? focusOffset : anchorOffset;
                startOffset = offset;
                endOffset = undefined;
            } else if (isLast) {
                const offset = isBackward ? anchorOffset : focusOffset;
                startOffset = 0;
                endOffset = offset;
            }
            // NOTE: This mutates __text directly because the primary use case is to
            // modify a $cloneWithProperties node that should never be added
            // to the EditorState so we must not call getWritable via setTextContent
            const text = textNode.__text.slice(startOffset, endOffset);
            if (text !== textNode.__text) {
                if (mutates === 'clone') {
                    textNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$cloneWithPropertiesEphemeral"])(textNode);
                }
                textNode.__text = text;
            }
        }
    }
    return textNode;
}
/**
 * Determines if the current selection is at the end of the node.
 * @param point - The point of the selection to test.
 * @returns true if the provided point offset is in the last possible position, false otherwise.
 */ function $isAtNodeEnd(point) {
    if (point.type === 'text') {
        return point.offset === point.getNode().getTextContentSize();
    }
    const node = point.getNode();
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node)) {
        formatDevErrorMessage(`isAtNodeEnd: node must be a TextNode or ElementNode`);
    }
    return point.offset === node.getChildrenSize();
}
/**
 * Trims text from a node in order to shorten it, eg. to enforce a text's max length. If it deletes text
 * that is an ancestor of the anchor then it will leave 2 indents, otherwise, if no text content exists, it deletes
 * the TextNode. It will move the focus to either the end of any left over text or beginning of a new TextNode.
 * @param editor - The lexical editor.
 * @param anchor - The anchor of the current selection, where the selection should be pointing.
 * @param delCount - The amount of characters to delete. Useful as a dynamic variable eg. textContentSize - maxLength;
 */ function $trimTextContentFromAnchor(editor, anchor, delCount) {
    // Work from the current selection anchor point
    let currentNode = anchor.getNode();
    let remaining = delCount;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode)) {
        const descendantNode = currentNode.getDescendantByIndex(anchor.offset);
        if (descendantNode !== null) {
            currentNode = descendantNode;
        }
    }
    while(remaining > 0 && currentNode !== null){
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode)) {
            const lastDescendant = currentNode.getLastDescendant();
            if (lastDescendant !== null) {
                currentNode = lastDescendant;
            }
        }
        let nextNode = currentNode.getPreviousSibling();
        let additionalElementWhitespace = 0;
        if (nextNode === null) {
            let parent = currentNode.getParentOrThrow();
            let parentSibling = parent.getPreviousSibling();
            while(parentSibling === null){
                parent = parent.getParent();
                if (parent === null) {
                    nextNode = null;
                    break;
                }
                parentSibling = parent.getPreviousSibling();
            }
            if (parent !== null) {
                additionalElementWhitespace = parent.isInline() ? 0 : 2;
                nextNode = parentSibling;
            }
        }
        let text = currentNode.getTextContent();
        // If the text is empty, we need to consider adding in two line breaks to match
        // the content if we were to get it from its parent.
        if (text === '' && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(currentNode) && !currentNode.isInline()) {
            // TODO: should this be handled in core?
            text = '\n\n';
        }
        const currentNodeSize = text.length;
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(currentNode) || remaining >= currentNodeSize) {
            const parent = currentNode.getParent();
            currentNode.remove();
            if (parent != null && parent.getChildrenSize() === 0 && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootNode"])(parent)) {
                parent.remove();
            }
            remaining -= currentNodeSize + additionalElementWhitespace;
            currentNode = nextNode;
        } else {
            const key = currentNode.getKey();
            // See if we can just revert it to what was in the last editor state
            const prevTextContent = editor.getEditorState().read(()=>{
                const prevNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getNodeByKey"])(key);
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(prevNode) && prevNode.isSimpleText()) {
                    return prevNode.getTextContent();
                }
                return null;
            });
            const offset = currentNodeSize - remaining;
            const slicedText = text.slice(0, offset);
            if (prevTextContent !== null && prevTextContent !== text) {
                const prevSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getPreviousSelection"])();
                let target = currentNode;
                if (!currentNode.isSimpleText()) {
                    const textNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createTextNode"])(prevTextContent);
                    currentNode.replace(textNode);
                    target = textNode;
                } else {
                    currentNode.setTextContent(prevTextContent);
                }
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(prevSelection) && prevSelection.isCollapsed()) {
                    const prevOffset = prevSelection.anchor.offset;
                    target.select(prevOffset, prevOffset);
                }
            } else if (currentNode.isSimpleText()) {
                // Split text
                const isSelected = anchor.key === key;
                let anchorOffset = anchor.offset;
                // Move offset to end if it's less than the remaining number, otherwise
                // we'll have a negative splitStart.
                if (anchorOffset < remaining) {
                    anchorOffset = currentNodeSize;
                }
                const splitStart = isSelected ? anchorOffset - remaining : 0;
                const splitEnd = isSelected ? anchorOffset : offset;
                if (isSelected && splitStart === 0) {
                    const [excessNode] = currentNode.splitText(splitStart, splitEnd);
                    excessNode.remove();
                } else {
                    const [, excessNode] = currentNode.splitText(splitStart, splitEnd);
                    excessNode.remove();
                }
            } else {
                const textNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createTextNode"])(slicedText);
                currentNode.replace(textNode);
            }
            remaining = 0;
        }
    }
}
/**
 * Gets the TextNode's style object and adds the styles to the CSS.
 * @param node - The TextNode to add styles to.
 */ function $addNodeStyle(node) {
    const CSSText = node.getStyle();
    const styles = getStyleObjectFromRawCSS(CSSText);
    CSS_TO_STYLES.set(CSSText, styles);
}
/**
 * Applies the provided styles to the given TextNode, ElementNode, or
 * collapsed RangeSelection.
 *
 * @param target - The TextNode, ElementNode, or collapsed RangeSelection to apply the styles to
 * @param patch - The patch to apply, which can include multiple styles. \\{CSSProperty: value\\} . Can also accept a function that returns the new property value.
 */ function $patchStyle(target, patch) {
    if (!((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(target) ? target.isCollapsed() : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(target) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(target))) {
        formatDevErrorMessage(`$patchStyle must only be called with a TextNode, ElementNode, or collapsed RangeSelection`);
    }
    const prevStyles = getStyleObjectFromCSS((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(target) ? target.style : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(target) ? target.getStyle() : target.getTextStyle());
    const newStyles = Object.entries(patch).reduce((styles, [key, value])=>{
        if (typeof value === 'function') {
            styles[key] = value(prevStyles[key], target);
        } else if (value === null) {
            delete styles[key];
        } else {
            styles[key] = value;
        }
        return styles;
    }, {
        ...prevStyles
    });
    const newCSSText = getCSSFromStyleObject(newStyles);
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(target) || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(target)) {
        target.setStyle(newCSSText);
    } else {
        target.setTextStyle(newCSSText);
    }
    CSS_TO_STYLES.set(newCSSText, newStyles);
}
/**
 * Applies the provided styles to the TextNodes in the provided Selection.
 * Will update partially selected TextNodes by splitting the TextNode and applying
 * the styles to the appropriate one.
 * @param selection - The selected node(s) to update.
 * @param patch - The patch to apply, which can include multiple styles. \\{CSSProperty: value\\} . Can also accept a function that returns the new property value.
 */ function $patchStyleText(selection, patch) {
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed()) {
        $patchStyle(selection, patch);
        const emptyNode = selection.anchor.getNode();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(emptyNode) && emptyNode.isEmpty()) {
            $patchStyle(emptyNode, patch);
        }
    }
    $forEachSelectedTextNode((textNode)=>{
        $patchStyle(textNode, patch);
    });
    const nodes = selection.getNodes();
    if (nodes.length > 0) {
        const patchedElementKeys = new Set();
        for (const node of nodes){
            if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) || !node.canBeEmpty() || node.getChildrenSize() !== 0) {
                continue;
            }
            const key = node.getKey();
            if (patchedElementKeys.has(key)) {
                continue;
            }
            patchedElementKeys.add(key);
            $patchStyle(node, patch);
        }
    }
}
function $forEachSelectedTextNode(fn) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if (!selection) {
        return;
    }
    const slicedTextNodes = new Map();
    const getSliceIndices = (node)=>slicedTextNodes.get(node.getKey()) || [
            0,
            node.getTextContentSize()
        ];
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        for (const slice of (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$caretRangeFromSelection"])(selection).getTextSlices()){
            if (slice) {
                slicedTextNodes.set(slice.caret.origin.getKey(), slice.getSliceIndices());
            }
        }
    }
    const selectedNodes = selection.getNodes();
    for (const selectedNode of selectedNodes){
        if (!((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(selectedNode) && selectedNode.canHaveFormat())) {
            continue;
        }
        const [startOffset, endOffset] = getSliceIndices(selectedNode);
        // No actual text is selected, so do nothing.
        if (endOffset === startOffset) {
            continue;
        }
        // The entire node is selected or a token/segment, so just format it
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTokenOrSegmented"])(selectedNode) || startOffset === 0 && endOffset === selectedNode.getTextContentSize()) {
            fn(selectedNode);
        } else {
            // The node is partially selected, so split it into two or three nodes
            // and style the selected one.
            const splitNodes = selectedNode.splitText(startOffset, endOffset);
            const replacement = splitNodes[startOffset === 0 ? 0 : 1];
            fn(replacement);
        }
    }
    // Prior to NodeCaret #7046 this would have been a side-effect
    // so we do this for test compatibility.
    // TODO: we may want to consider simplifying by removing this
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.anchor.type === 'text' && selection.focus.type === 'text' && selection.anchor.key === selection.focus.key) {
        $ensureForwardRangeSelection(selection);
    }
}
/**
 * Ensure that the given RangeSelection is not backwards. If it
 * is backwards, then the anchor and focus points will be swapped
 * in-place. Ensuring that the selection is a writable RangeSelection
 * is the responsibility of the caller (e.g. in a read-only context
 * you will want to clone $getSelection() before using this).
 *
 * @param selection a writable RangeSelection
 */ function $ensureForwardRangeSelection(selection) {
    if (selection.isBackward()) {
        const { anchor, focus } = selection;
        // stash for the in-place swap
        const { key, offset, type } = anchor;
        anchor.set(focus.key, focus.offset, focus.type);
        focus.set(key, offset, type);
    }
}
function $copyBlockFormatIndent(srcNode, destNode) {
    const format = srcNode.getFormatType();
    const indent = srcNode.getIndent();
    if (format !== destNode.getFormatType()) {
        destNode.setFormat(format);
    }
    if (indent !== destNode.getIndent()) {
        destNode.setIndent(indent);
    }
}
/**
 * Converts all nodes in the selection that are of one block type to another.
 * @param selection - The selected blocks to be converted.
 * @param $createElement - The function that creates the node. eg. $createParagraphNode.
 * @param $afterCreateElement - The function that updates the new node based on the previous one ($copyBlockFormatIndent by default)
 */ function $setBlocksType(selection, $createElement, $afterCreateElement = $copyBlockFormatIndent) {
    if (selection === null) {
        return;
    }
    // Selections tend to not include their containing blocks so we effectively
    // expand it here
    const anchorAndFocus = selection.getStartEndPoints();
    const blockMap = new Map();
    let newSelection = null;
    if (anchorAndFocus) {
        const [anchor, focus] = anchorAndFocus;
        newSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createRangeSelection"])();
        newSelection.anchor.set(anchor.key, anchor.offset, anchor.type);
        newSelection.focus.set(focus.key, focus.offset, focus.type);
        const anchorBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(anchor.getNode(), __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INTERNAL_$isBlock"]);
        const focusBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(focus.getNode(), __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INTERNAL_$isBlock"]);
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(anchorBlock)) {
            blockMap.set(anchorBlock.getKey(), anchorBlock);
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(focusBlock)) {
            blockMap.set(focusBlock.getKey(), focusBlock);
        }
    }
    for (const node of selection.getNodes()){
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INTERNAL_$isBlock"])(node)) {
            blockMap.set(node.getKey(), node);
        } else if (anchorAndFocus === null) {
            const ancestorBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(node, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["INTERNAL_$isBlock"]);
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(ancestorBlock)) {
                blockMap.set(ancestorBlock.getKey(), ancestorBlock);
            }
        }
    }
    for (const [key, prevNode] of blockMap){
        const element = $createElement();
        $afterCreateElement(prevNode, element);
        prevNode.replace(element, true);
        if (newSelection) {
            if (key === newSelection.anchor.key) {
                newSelection.anchor.set(element.getKey(), newSelection.anchor.offset, newSelection.anchor.type);
            }
            if (key === newSelection.focus.key) {
                newSelection.focus.set(element.getKey(), newSelection.focus.offset, newSelection.focus.type);
            }
        }
    }
    if (newSelection && selection.is((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])())) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelection"])(newSelection);
    }
}
function isPointAttached(point) {
    return point.getNode().isAttached();
}
function $removeParentEmptyElements(startingNode) {
    let node = startingNode;
    while(node !== null && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(node)){
        const latest = node.getLatest();
        const parentNode = node.getParent();
        if (latest.getChildrenSize() === 0) {
            node.remove(true);
        }
        node = parentNode;
    }
}
/**
 * @deprecated In favor of $setBlockTypes
 * Wraps all nodes in the selection into another node of the type returned by createElement.
 * @param selection - The selection of nodes to be wrapped.
 * @param createElement - A function that creates the wrapping ElementNode. eg. $createParagraphNode.
 * @param wrappingElement - An element to append the wrapped selection and its children to.
 */ function $wrapNodes(selection, createElement, wrappingElement = null) {
    const anchorAndFocus = selection.getStartEndPoints();
    const anchor = anchorAndFocus ? anchorAndFocus[0] : null;
    const nodes = selection.getNodes();
    const nodesLength = nodes.length;
    if (anchor !== null && (nodesLength === 0 || nodesLength === 1 && anchor.type === 'element' && anchor.getNode().getChildrenSize() === 0)) {
        const target = anchor.type === 'text' ? anchor.getNode().getParentOrThrow() : anchor.getNode();
        const children = target.getChildren();
        let element = createElement();
        element.setFormat(target.getFormatType());
        element.setIndent(target.getIndent());
        children.forEach((child)=>element.append(child));
        if (wrappingElement) {
            element = wrappingElement.append(element);
        }
        target.replace(element);
        return;
    }
    let topLevelNode = null;
    let descendants = [];
    for(let i = 0; i < nodesLength; i++){
        const node = nodes[i];
        // Determine whether wrapping has to be broken down into multiple chunks. This can happen if the
        // user selected multiple Root-like nodes that have to be treated separately as if they are
        // their own branch. I.e. you don't want to wrap a whole table, but rather the contents of each
        // of each of the cell nodes.
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(node)) {
            $wrapNodesImpl(selection, descendants, descendants.length, createElement, wrappingElement);
            descendants = [];
            topLevelNode = node;
        } else if (topLevelNode === null || topLevelNode !== null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$hasAncestor"])(node, topLevelNode)) {
            descendants.push(node);
        } else {
            $wrapNodesImpl(selection, descendants, descendants.length, createElement, wrappingElement);
            descendants = [
                node
            ];
        }
    }
    $wrapNodesImpl(selection, descendants, descendants.length, createElement, wrappingElement);
}
/**
 * Wraps each node into a new ElementNode.
 * @param selection - The selection of nodes to wrap.
 * @param nodes - An array of nodes, generally the descendants of the selection.
 * @param nodesLength - The length of nodes.
 * @param createElement - A function that creates the wrapping ElementNode. eg. $createParagraphNode.
 * @param wrappingElement - An element to wrap all the nodes into.
 * @returns
 */ function $wrapNodesImpl(selection, nodes, nodesLength, createElement, wrappingElement = null) {
    if (nodes.length === 0) {
        return;
    }
    const firstNode = nodes[0];
    const elementMapping = new Map();
    const elements = [];
    // The below logic is to find the right target for us to
    // either insertAfter/insertBefore/append the corresponding
    // elements to. This is made more complicated due to nested
    // structures.
    let target = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(firstNode) ? firstNode : firstNode.getParentOrThrow();
    if (target.isInline()) {
        target = target.getParentOrThrow();
    }
    let targetIsPrevSibling = false;
    while(target !== null){
        const prevSibling = target.getPreviousSibling();
        if (prevSibling !== null) {
            target = prevSibling;
            targetIsPrevSibling = true;
            break;
        }
        target = target.getParentOrThrow();
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(target)) {
            break;
        }
    }
    const emptyElements = new Set();
    // Find any top level empty elements
    for(let i = 0; i < nodesLength; i++){
        const node = nodes[i];
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && node.getChildrenSize() === 0) {
            emptyElements.add(node.getKey());
        }
    }
    const movedNodes = new Set();
    // Move out all leaf nodes into our elements array.
    // If we find a top level empty element, also move make
    // an element for that.
    for(let i = 0; i < nodesLength; i++){
        const node = nodes[i];
        let parent = node.getParent();
        if (parent !== null && parent.isInline()) {
            parent = parent.getParent();
        }
        if (parent !== null && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isLeafNode"])(node) && !movedNodes.has(node.getKey())) {
            const parentKey = parent.getKey();
            if (elementMapping.get(parentKey) === undefined) {
                const targetElement = createElement();
                targetElement.setFormat(parent.getFormatType());
                targetElement.setIndent(parent.getIndent());
                elements.push(targetElement);
                elementMapping.set(parentKey, targetElement);
                // Move node and its siblings to the new
                // element.
                parent.getChildren().forEach((child)=>{
                    targetElement.append(child);
                    movedNodes.add(child.getKey());
                    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(child)) {
                        // Skip nested leaf nodes if the parent has already been moved
                        child.getChildrenKeys().forEach((key)=>movedNodes.add(key));
                    }
                });
                $removeParentEmptyElements(parent);
            }
        } else if (emptyElements.has(node.getKey())) {
            if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node)) {
                formatDevErrorMessage(`Expected node in emptyElements to be an ElementNode`);
            }
            const targetElement = createElement();
            targetElement.setFormat(node.getFormatType());
            targetElement.setIndent(node.getIndent());
            elements.push(targetElement);
            node.remove(true);
        }
    }
    if (wrappingElement !== null) {
        for(let i = 0; i < elements.length; i++){
            const element = elements[i];
            wrappingElement.append(element);
        }
    }
    let lastElement = null;
    // If our target is Root-like, let's see if we can re-adjust
    // so that the target is the first child instead.
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRootOrShadowRoot"])(target)) {
        if (targetIsPrevSibling) {
            if (wrappingElement !== null) {
                target.insertAfter(wrappingElement);
            } else {
                for(let i = elements.length - 1; i >= 0; i--){
                    const element = elements[i];
                    target.insertAfter(element);
                }
            }
        } else {
            const firstChild = target.getFirstChild();
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(firstChild)) {
                target = firstChild;
            }
            if (firstChild === null) {
                if (wrappingElement) {
                    target.append(wrappingElement);
                } else {
                    for(let i = 0; i < elements.length; i++){
                        const element = elements[i];
                        target.append(element);
                        lastElement = element;
                    }
                }
            } else {
                if (wrappingElement !== null) {
                    firstChild.insertBefore(wrappingElement);
                } else {
                    for(let i = 0; i < elements.length; i++){
                        const element = elements[i];
                        firstChild.insertBefore(element);
                        lastElement = element;
                    }
                }
            }
        }
    } else {
        if (wrappingElement) {
            target.insertAfter(wrappingElement);
        } else {
            for(let i = elements.length - 1; i >= 0; i--){
                const element = elements[i];
                target.insertAfter(element);
                lastElement = element;
            }
        }
    }
    const prevSelection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getPreviousSelection"])();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(prevSelection) && isPointAttached(prevSelection.anchor) && isPointAttached(prevSelection.focus)) {
        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelection"])(prevSelection.clone());
    } else if (lastElement !== null) {
        lastElement.selectEnd();
    } else {
        selection.dirty = true;
    }
}
/**
 * Tests if the selection's parent element has vertical writing mode.
 * @param selection - The selection whose parent to test.
 * @returns true if the selection's parent has vertical writing mode (writing-mode: vertical-rl), false otherwise.
 */ function $isEditorVerticalOrientation(selection) {
    const computedStyle = $getComputedStyle(selection);
    return computedStyle !== null && computedStyle.writingMode === 'vertical-rl';
}
/**
 * Gets the computed DOM styles of the parent of the selection's anchor node.
 * @param selection - The selection to check the styles for.
 * @returns the computed styles of the node or null if there is no DOM element or no default view for the document.
 */ function $getComputedStyle(selection) {
    const anchorNode = selection.anchor.getNode();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(anchorNode)) {
        return $getComputedStyleForElement(anchorNode);
    }
    return $getComputedStyleForParent(anchorNode);
}
/**
 * Determines if the default character selection should be overridden. Used with DecoratorNodes
 * @param selection - The selection whose default character selection may need to be overridden.
 * @param isBackward - Is the selection backwards (the focus comes before the anchor)?
 * @returns true if it should be overridden, false if not.
 */ function $shouldOverrideDefaultCharacterSelection(selection, isBackward) {
    const isVertical = $isEditorVerticalOrientation(selection);
    // In vertical writing mode, we adjust the direction for correct caret movement
    let adjustedIsBackward = isVertical ? !isBackward : isBackward;
    // In right-to-left writing mode, we invert the direction for correct caret movement
    if ($isParentElementRTL(selection)) {
        adjustedIsBackward = !adjustedIsBackward;
    }
    const focusCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$caretFromPoint"])(selection.focus, adjustedIsBackward ? 'previous' : 'next');
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isExtendableTextPointCaret"])(focusCaret)) {
        return false;
    }
    for (const nextCaret of (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$extendCaretToRange"])(focusCaret)){
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isChildCaret"])(nextCaret)) {
            return !nextCaret.origin.isInline();
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(nextCaret.origin)) {
            continue;
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isDecoratorNode"])(nextCaret.origin)) {
            return true;
        }
        break;
    }
    return false;
}
/**
 * Moves the selection according to the arguments.
 * @param selection - The selected text or nodes.
 * @param isHoldingShift - Is the shift key being held down during the operation.
 * @param isBackward - Is the selection selected backwards (the focus comes before the anchor)?
 * @param granularity - The distance to adjust the current selection.
 */ function $moveCaretSelection(selection, isHoldingShift, isBackward, granularity) {
    selection.modify(isHoldingShift ? 'extend' : 'move', isBackward, granularity);
}
/**
 * Tests a parent element for right to left direction.
 * @param selection - The selection whose parent is to be tested.
 * @returns true if the selections' parent element has a direction of 'rtl' (right to left), false otherwise.
 */ function $isParentElementRTL(selection) {
    const computedStyle = $getComputedStyle(selection);
    return computedStyle !== null && computedStyle.direction === 'rtl';
}
/**
 * Moves selection by character according to arguments.
 * @param selection - The selection of the characters to move.
 * @param isHoldingShift - Is the shift key being held down during the operation.
 * @param isBackward - Is the selection backward (the focus comes before the anchor)?
 */ function $moveCharacter(selection, isHoldingShift, isBackward) {
    const isRTL = $isParentElementRTL(selection);
    const isVertical = $isEditorVerticalOrientation(selection);
    // In vertical-rl writing mode, arrow key directions need to be flipped
    // to match the visual flow of text (top to bottom, right to left)
    let adjustedIsBackward;
    if (isVertical) {
        // In vertical-rl mode, we need to completely invert the direction
        // Left arrow (backward) should move down (forward)
        // Right arrow (forward) should move up (backward)
        adjustedIsBackward = !isBackward;
    } else if (isRTL) {
        // In horizontal RTL mode, use the standard RTL behavior
        adjustedIsBackward = !isBackward;
    } else {
        // Standard LTR horizontal text
        adjustedIsBackward = isBackward;
    }
    // Apply the direction adjustment to move the caret
    $moveCaretSelection(selection, isHoldingShift, adjustedIsBackward, 'character');
}
/**
 * Returns the current value of a CSS property for Nodes, if set. If not set, it returns the defaultValue.
 * @param node - The node whose style value to get.
 * @param styleProperty - The CSS style property.
 * @param defaultValue - The default value for the property.
 * @returns The value of the property for node.
 */ function $getNodeStyleValueForProperty(node, styleProperty, defaultValue) {
    const css = node.getStyle();
    const styleObject = getStyleObjectFromCSS(css);
    if (styleObject !== null) {
        return styleObject[styleProperty] || defaultValue;
    }
    return defaultValue;
}
/**
 * Returns the current value of a CSS property for TextNodes in the Selection, if set. If not set, it returns the defaultValue.
 * If all TextNodes do not have the same value, it returns an empty string.
 * @param selection - The selection of TextNodes whose value to find.
 * @param styleProperty - The CSS style property.
 * @param defaultValue - The default value for the property, defaults to an empty string.
 * @returns The value of the property for the selected TextNodes.
 */ function $getSelectionStyleValueForProperty(selection, styleProperty, defaultValue = '') {
    let styleValue = null;
    const nodes = selection.getNodes();
    const anchor = selection.anchor;
    const focus = selection.focus;
    const isBackward = selection.isBackward();
    const endOffset = isBackward ? focus.offset : anchor.offset;
    const endNode = isBackward ? focus.getNode() : anchor.getNode();
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection) && selection.isCollapsed() && selection.style !== '') {
        const css = selection.style;
        const styleObject = getStyleObjectFromCSS(css);
        if (styleObject !== null && styleProperty in styleObject) {
            return styleObject[styleProperty];
        }
    }
    for(let i = 0; i < nodes.length; i++){
        const node = nodes[i];
        // if no actual characters in the end node are selected, we don't
        // include it in the selection for purposes of determining style
        // value
        if (i !== 0 && endOffset === 0 && node.is(endNode)) {
            continue;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextNode"])(node)) {
            const nodeStyleValue = $getNodeStyleValueForProperty(node, styleProperty, defaultValue);
            if (styleValue === null) {
                styleValue = nodeStyleValue;
            } else if (styleValue !== nodeStyleValue) {
                // multiple text nodes are in the selection and they don't all
                // have the same style.
                styleValue = '';
                break;
            }
        }
    }
    return styleValue === null ? defaultValue : styleValue;
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ /** @deprecated renamed to {@link $trimTextContentFromAnchor} by @lexical/eslint-plugin rules-of-lexical */ const trimTextContentFromAnchor = $trimTextContentFromAnchor;
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/utils/LexicalUtils.dev.mjs [app-rsc] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "$descendantsMatching",
    ()=>$descendantsMatching,
    "$dfs",
    ()=>$dfs,
    "$dfsIterator",
    ()=>$dfsIterator,
    "$filter",
    ()=>$filter,
    "$firstToLastIterator",
    ()=>$firstToLastIterator,
    "$getAdjacentCaret",
    ()=>$getAdjacentCaret,
    "$getDepth",
    ()=>$getDepth,
    "$getNearestBlockElementAncestorOrThrow",
    ()=>$getNearestBlockElementAncestorOrThrow,
    "$getNearestNodeOfType",
    ()=>$getNearestNodeOfType,
    "$getNextRightPreorderNode",
    ()=>$getNextRightPreorderNode,
    "$getNextSiblingOrParentSibling",
    ()=>$getNextSiblingOrParentSibling,
    "$handleIndentAndOutdent",
    ()=>$handleIndentAndOutdent,
    "$insertFirst",
    ()=>$insertFirst,
    "$insertNodeToNearestRoot",
    ()=>$insertNodeToNearestRoot,
    "$insertNodeToNearestRootAtCaret",
    ()=>$insertNodeToNearestRootAtCaret,
    "$isEditorIsNestedEditor",
    ()=>$isEditorIsNestedEditor,
    "$lastToFirstIterator",
    ()=>$lastToFirstIterator,
    "$restoreEditorState",
    ()=>$restoreEditorState,
    "$reverseDfs",
    ()=>$reverseDfs,
    "$reverseDfsIterator",
    ()=>$reverseDfsIterator,
    "$unwrapAndFilterDescendants",
    ()=>$unwrapAndFilterDescendants,
    "$unwrapNode",
    ()=>$unwrapNode,
    "$wrapNodeInElement",
    ()=>$wrapNodeInElement,
    "CAN_USE_BEFORE_INPUT",
    ()=>CAN_USE_BEFORE_INPUT,
    "CAN_USE_DOM",
    ()=>CAN_USE_DOM,
    "IS_ANDROID",
    ()=>IS_ANDROID,
    "IS_ANDROID_CHROME",
    ()=>IS_ANDROID_CHROME,
    "IS_APPLE",
    ()=>IS_APPLE,
    "IS_APPLE_WEBKIT",
    ()=>IS_APPLE_WEBKIT,
    "IS_CHROME",
    ()=>IS_CHROME,
    "IS_FIREFOX",
    ()=>IS_FIREFOX,
    "IS_IOS",
    ()=>IS_IOS,
    "IS_SAFARI",
    ()=>IS_SAFARI,
    "calculateZoomLevel",
    ()=>calculateZoomLevel,
    "isMimeType",
    ()=>isMimeType,
    "makeStateWrapper",
    ()=>makeStateWrapper,
    "markSelection",
    ()=>markSelection,
    "mediaFileReader",
    ()=>mediaFileReader,
    "objectKlassEquals",
    ()=>objectKlassEquals,
    "positionNodeOnRange",
    ()=>mlcPositionNodeOnRange,
    "registerNestedElementResolver",
    ()=>registerNestedElementResolver,
    "selectionAlwaysOnDisplay",
    ()=>selectionAlwaysOnDisplay
]);
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/lexical/Lexical.dev.mjs [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@lexical/selection/LexicalSelection.dev.mjs [app-rsc] (ecmascript) <locals>");
;
;
;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ // Do not require this module directly! Use normal `invariant` calls.
function formatDevErrorMessage(message) {
    throw new Error(message);
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const CAN_USE_DOM$1 = ("TURBOPACK compile-time value", "undefined") !== 'undefined' && typeof window.document !== 'undefined' && typeof window.document.createElement !== 'undefined';
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ const documentMode = ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : null;
const IS_APPLE$1 = CAN_USE_DOM$1 && /Mac|iPod|iPhone|iPad/.test(navigator.platform);
const IS_FIREFOX$1 = CAN_USE_DOM$1 && /^(?!.*Seamonkey)(?=.*Firefox).*/i.test(navigator.userAgent);
const CAN_USE_BEFORE_INPUT$1 = ("TURBOPACK compile-time falsy", 0) ? "TURBOPACK unreachable" : false;
const IS_SAFARI$1 = CAN_USE_DOM$1 && /Version\/[\d.]+.*Safari/.test(navigator.userAgent);
const IS_IOS$1 = CAN_USE_DOM$1 && /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
const IS_ANDROID$1 = CAN_USE_DOM$1 && /Android/.test(navigator.userAgent);
// Keep these in case we need to use them in the future.
// export const IS_WINDOWS: boolean = CAN_USE_DOM && /Win/.test(navigator.platform);
const IS_CHROME$1 = CAN_USE_DOM$1 && /^(?=.*Chrome).*/i.test(navigator.userAgent);
// export const canUseTextInputEvent: boolean = CAN_USE_DOM && 'TextEvent' in window && !documentMode;
const IS_ANDROID_CHROME$1 = CAN_USE_DOM$1 && IS_ANDROID$1 && IS_CHROME$1;
const IS_APPLE_WEBKIT$1 = CAN_USE_DOM$1 && /AppleWebKit\/[\d.]+/.test(navigator.userAgent) && IS_APPLE$1 && !IS_CHROME$1;
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function px(value) {
    return `${value}px`;
}
const mutationObserverConfig = {
    attributes: true,
    characterData: true,
    childList: true,
    subtree: true
};
function prependDOMNode(parent, node) {
    parent.insertBefore(node, parent.firstChild);
}
/**
 * Place one or multiple newly created Nodes at the passed Range's position.
 * Multiple nodes will only be created when the Range spans multiple lines (aka
 * client rects).
 *
 * This function can come particularly useful to highlight particular parts of
 * the text without interfering with the EditorState, that will often replicate
 * the state across collab and clipboard.
 *
 * This function accounts for DOM updates which can modify the passed Range.
 * Hence, the function return to remove the listener.
 */ function mlcPositionNodeOnRange(editor, range, onReposition) {
    let rootDOMNode = null;
    let parentDOMNode = null;
    let observer = null;
    let lastNodes = [];
    const wrapperNode = document.createElement('div');
    wrapperNode.style.position = 'relative';
    function position() {
        if (!(rootDOMNode !== null)) {
            formatDevErrorMessage(`Unexpected null rootDOMNode`);
        }
        if (!(parentDOMNode !== null)) {
            formatDevErrorMessage(`Unexpected null parentDOMNode`);
        }
        const { left: parentLeft, top: parentTop } = parentDOMNode.getBoundingClientRect();
        const rects = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$lexical$2f$selection$2f$LexicalSelection$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__["createRectsFromDOMRange"])(editor, range);
        if (!wrapperNode.isConnected) {
            prependDOMNode(parentDOMNode, wrapperNode);
        }
        let hasRepositioned = false;
        for(let i = 0; i < rects.length; i++){
            const rect = rects[i];
            // Try to reuse the previously created Node when possible, no need to
            // remove/create on the most common case reposition case
            const rectNode = lastNodes[i] || document.createElement('div');
            const rectNodeStyle = rectNode.style;
            if (rectNodeStyle.position !== 'absolute') {
                rectNodeStyle.position = 'absolute';
                hasRepositioned = true;
            }
            const left = px(rect.left - parentLeft);
            if (rectNodeStyle.left !== left) {
                rectNodeStyle.left = left;
                hasRepositioned = true;
            }
            const top = px(rect.top - parentTop);
            if (rectNodeStyle.top !== top) {
                rectNode.style.top = top;
                hasRepositioned = true;
            }
            const width = px(rect.width);
            if (rectNodeStyle.width !== width) {
                rectNode.style.width = width;
                hasRepositioned = true;
            }
            const height = px(rect.height);
            if (rectNodeStyle.height !== height) {
                rectNode.style.height = height;
                hasRepositioned = true;
            }
            if (rectNode.parentNode !== wrapperNode) {
                wrapperNode.append(rectNode);
                hasRepositioned = true;
            }
            lastNodes[i] = rectNode;
        }
        while(lastNodes.length > rects.length){
            lastNodes.pop();
        }
        if (hasRepositioned) {
            onReposition(lastNodes);
        }
    }
    function stop() {
        parentDOMNode = null;
        rootDOMNode = null;
        if (observer !== null) {
            observer.disconnect();
        }
        observer = null;
        wrapperNode.remove();
        for (const node of lastNodes){
            node.remove();
        }
        lastNodes = [];
    }
    function restart() {
        const currentRootDOMNode = editor.getRootElement();
        if (currentRootDOMNode === null) {
            return stop();
        }
        const currentParentDOMNode = currentRootDOMNode.parentElement;
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isHTMLElement"])(currentParentDOMNode)) {
            return stop();
        }
        stop();
        rootDOMNode = currentRootDOMNode;
        parentDOMNode = currentParentDOMNode;
        observer = new MutationObserver((mutations)=>{
            const nextRootDOMNode = editor.getRootElement();
            const nextParentDOMNode = nextRootDOMNode && nextRootDOMNode.parentElement;
            if (nextRootDOMNode !== rootDOMNode || nextParentDOMNode !== parentDOMNode) {
                return restart();
            }
            for (const mutation of mutations){
                if (!wrapperNode.contains(mutation.target)) {
                    // TODO throttle
                    return position();
                }
            }
        });
        observer.observe(currentParentDOMNode, mutationObserverConfig);
        position();
    }
    const removeRootListener = editor.registerRootListener(restart);
    return ()=>{
        removeRootListener();
        stop();
    };
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function $getOrderedSelectionPoints(selection) {
    const points = selection.getStartEndPoints();
    return selection.isBackward() ? [
        points[1],
        points[0]
    ] : points;
}
function rangeTargetFromPoint(point, node, dom) {
    if (point.type === 'text' || !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node)) {
        const textDOM = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getDOMTextNode"])(dom) || dom;
        return [
            textDOM,
            point.offset
        ];
    } else {
        const slot = node.getDOMSlot(dom);
        return [
            slot.element,
            slot.getFirstChildOffset() + point.offset
        ];
    }
}
function rangeFromPoints(editor, start, startNode, startDOM, end, endNode, endDOM) {
    const editorDocument = editor._window ? editor._window.document : document;
    const range = editorDocument.createRange();
    range.setStart(...rangeTargetFromPoint(start, startNode, startDOM));
    range.setEnd(...rangeTargetFromPoint(end, endNode, endDOM));
    return range;
}
/**
 * Place one or multiple newly created Nodes at the current selection. Multiple
 * nodes will only be created when the selection spans multiple lines (aka
 * client rects).
 *
 * This function can come useful when you want to show the selection but the
 * editor has been focused away.
 */ function markSelection(editor, onReposition) {
    let previousAnchorNode = null;
    let previousAnchorNodeDOM = null;
    let previousAnchorOffset = null;
    let previousFocusNode = null;
    let previousFocusNodeDOM = null;
    let previousFocusOffset = null;
    let removeRangeListener = ()=>{};
    function compute(editorState) {
        editorState.read(()=>{
            const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
            if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
                // TODO
                previousAnchorNode = null;
                previousAnchorOffset = null;
                previousFocusNode = null;
                previousFocusOffset = null;
                removeRangeListener();
                removeRangeListener = ()=>{};
                return;
            }
            const [start, end] = $getOrderedSelectionPoints(selection);
            const currentStartNode = start.getNode();
            const currentStartNodeKey = currentStartNode.getKey();
            const currentStartOffset = start.offset;
            const currentEndNode = end.getNode();
            const currentEndNodeKey = currentEndNode.getKey();
            const currentEndOffset = end.offset;
            const currentStartNodeDOM = editor.getElementByKey(currentStartNodeKey);
            const currentEndNodeDOM = editor.getElementByKey(currentEndNodeKey);
            const differentStartDOM = previousAnchorNode === null || currentStartNodeDOM !== previousAnchorNodeDOM || currentStartOffset !== previousAnchorOffset || currentStartNodeKey !== previousAnchorNode.getKey();
            const differentEndDOM = previousFocusNode === null || currentEndNodeDOM !== previousFocusNodeDOM || currentEndOffset !== previousFocusOffset || currentEndNodeKey !== previousFocusNode.getKey();
            if ((differentStartDOM || differentEndDOM) && currentStartNodeDOM !== null && currentEndNodeDOM !== null) {
                const range = rangeFromPoints(editor, start, currentStartNode, currentStartNodeDOM, end, currentEndNode, currentEndNodeDOM);
                removeRangeListener();
                removeRangeListener = mlcPositionNodeOnRange(editor, range, (domNodes)=>{
                    if (onReposition === undefined) {
                        for (const domNode of domNodes){
                            const domNodeStyle = domNode.style;
                            if (domNodeStyle.background !== 'Highlight') {
                                domNodeStyle.background = 'Highlight';
                            }
                            if (domNodeStyle.color !== 'HighlightText') {
                                domNodeStyle.color = 'HighlightText';
                            }
                            if (domNodeStyle.marginTop !== px(-1.5)) {
                                domNodeStyle.marginTop = px(-1.5);
                            }
                            if (domNodeStyle.paddingTop !== px(4)) {
                                domNodeStyle.paddingTop = px(4);
                            }
                            if (domNodeStyle.paddingBottom !== px(0)) {
                                domNodeStyle.paddingBottom = px(0);
                            }
                        }
                    } else {
                        onReposition(domNodes);
                    }
                });
            }
            previousAnchorNode = currentStartNode;
            previousAnchorNodeDOM = currentStartNodeDOM;
            previousAnchorOffset = currentStartOffset;
            previousFocusNode = currentEndNode;
            previousFocusNodeDOM = currentEndNodeDOM;
            previousFocusOffset = currentEndOffset;
        });
    }
    compute(editor.getEditorState());
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["mergeRegister"])(editor.registerUpdateListener(({ editorState })=>compute(editorState)), ()=>{
        removeRangeListener();
    });
}
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */ function selectionAlwaysOnDisplay(editor, onReposition) {
    let removeSelectionMark = null;
    const onSelectionChange = ()=>{
        const domSelection = getSelection();
        const domAnchorNode = domSelection && domSelection.anchorNode;
        const editorRootElement = editor.getRootElement();
        const isSelectionInsideEditor = domAnchorNode !== null && editorRootElement !== null && editorRootElement.contains(domAnchorNode);
        if (isSelectionInsideEditor) {
            if (removeSelectionMark !== null) {
                removeSelectionMark();
                removeSelectionMark = null;
            }
        } else {
            if (removeSelectionMark === null) {
                removeSelectionMark = markSelection(editor, onReposition);
            }
        }
    };
    document.addEventListener('selectionchange', onSelectionChange);
    return ()=>{
        if (removeSelectionMark !== null) {
            removeSelectionMark();
        }
        document.removeEventListener('selectionchange', onSelectionChange);
    };
}
// Hotfix to export these with inlined types #5918
const CAN_USE_BEFORE_INPUT = CAN_USE_BEFORE_INPUT$1;
const CAN_USE_DOM = CAN_USE_DOM$1;
const IS_ANDROID = IS_ANDROID$1;
const IS_ANDROID_CHROME = IS_ANDROID_CHROME$1;
const IS_APPLE = IS_APPLE$1;
const IS_APPLE_WEBKIT = IS_APPLE_WEBKIT$1;
const IS_CHROME = IS_CHROME$1;
const IS_FIREFOX = IS_FIREFOX$1;
const IS_IOS = IS_IOS$1;
const IS_SAFARI = IS_SAFARI$1;
/**
 * Returns true if the file type matches the types passed within the acceptableMimeTypes array, false otherwise.
 * The types passed must be strings and are CASE-SENSITIVE.
 * eg. if file is of type 'text' and acceptableMimeTypes = ['TEXT', 'IMAGE'] the function will return false.
 * @param file - The file you want to type check.
 * @param acceptableMimeTypes - An array of strings of types which the file is checked against.
 * @returns true if the file is an acceptable mime type, false otherwise.
 */ function isMimeType(file, acceptableMimeTypes) {
    for (const acceptableType of acceptableMimeTypes){
        if (file.type.startsWith(acceptableType)) {
            return true;
        }
    }
    return false;
}
/**
 * Lexical File Reader with:
 *  1. MIME type support
 *  2. batched results (HistoryPlugin compatibility)
 *  3. Order aware (respects the order when multiple Files are passed)
 *
 * const filesResult = await mediaFileReader(files, ['image/']);
 * filesResult.forEach(file => editor.dispatchCommand('INSERT_IMAGE', \\{
 *   src: file.result,
 * \\}));
 */ function mediaFileReader(files, acceptableMimeTypes) {
    const filesIterator = files[Symbol.iterator]();
    return new Promise((resolve, reject)=>{
        const processed = [];
        const handleNextFile = ()=>{
            const { done, value: file } = filesIterator.next();
            if (done) {
                return resolve(processed);
            }
            const fileReader = new FileReader();
            fileReader.addEventListener('error', reject);
            fileReader.addEventListener('load', ()=>{
                const result = fileReader.result;
                if (typeof result === 'string') {
                    processed.push({
                        file,
                        result
                    });
                }
                handleNextFile();
            });
            if (isMimeType(file, acceptableMimeTypes)) {
                fileReader.readAsDataURL(file);
            } else {
                handleNextFile();
            }
        };
        handleNextFile();
    });
}
/**
 * "Depth-First Search" starts at the root/top node of a tree and goes as far as it can down a branch end
 * before backtracking and finding a new path. Consider solving a maze by hugging either wall, moving down a
 * branch until you hit a dead-end (leaf) and backtracking to find the nearest branching path and repeat.
 * It will then return all the nodes found in the search in an array of objects.
 * Preorder traversal is used, meaning that nodes are listed in the order of when they are FIRST encountered.
 * @param startNode - The node to start the search (inclusive), if omitted, it will start at the root node.
 * @param endNode - The node to end the search (inclusive), if omitted, it will find all descendants of the startingNode. If endNode
 * is an ElementNode, it will stop before visiting any of its children.
 * @returns An array of objects of all the nodes found by the search, including their depth into the tree.
 * \\{depth: number, node: LexicalNode\\} It will always return at least 1 node (the start node).
 */ function $dfs(startNode, endNode) {
    return Array.from($dfsIterator(startNode, endNode));
}
/**
 * Get the adjacent caret in the same direction
 *
 * @param caret A caret or null
 * @returns `caret.getAdjacentCaret()` or `null`
 */ function $getAdjacentCaret(caret) {
    return caret ? caret.getAdjacentCaret() : null;
}
/**
 * $dfs iterator (right to left). Tree traversal is done on the fly as new values are requested with O(1) memory.
 * @param startNode - The node to start the search, if omitted, it will start at the root node.
 * @param endNode - The node to end the search, if omitted, it will find all descendants of the startingNode.
 * @returns An iterator, each yielded value is a DFSNode. It will always return at least 1 node (the start node).
 */ function $reverseDfs(startNode, endNode) {
    return Array.from($reverseDfsIterator(startNode, endNode));
}
/**
 * $dfs iterator (left to right). Tree traversal is done on the fly as new values are requested with O(1) memory.
 * Preorder traversal is used, meaning that nodes are iterated over in the order of when they are FIRST encountered.
 * @param startNode - The node to start the search (inclusive), if omitted, it will start at the root node.
 * @param endNode - The node to end the search (inclusive), if omitted, it will find all descendants of the startingNode.
 * If endNode is an ElementNode, the iterator will end as soon as it reaches the endNode (no children will be visited).
 * @returns An iterator, each yielded value is a DFSNode. It will always return at least 1 node (the start node).
 */ function $dfsIterator(startNode, endNode) {
    return $dfsCaretIterator('next', startNode, endNode);
}
function $getEndCaret(startNode, direction) {
    const rval = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentSiblingOrParentSiblingCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(startNode, direction));
    return rval && rval[0];
}
function $dfsCaretIterator(direction, startNode, endNode) {
    const root = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])();
    const start = startNode || root;
    const startCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(start) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(start, direction) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(start, direction);
    const startDepth = $getDepth(start);
    const endCaret = endNode ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentChildCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaretOrSelf"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(endNode, direction))) || $getEndCaret(endNode, direction) : $getEndCaret(start, direction);
    let depth = startDepth;
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["makeStepwiseIterator"])({
        hasNext: (state)=>state !== null,
        initial: startCaret,
        map: (state)=>({
                depth,
                node: state.origin
            }),
        step: (state)=>{
            if (state.isSameNodeCaret(endCaret)) {
                return null;
            }
            if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isChildCaret"])(state)) {
                depth++;
            }
            const rval = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentSiblingOrParentSiblingCaret"])(state);
            if (!rval || rval[0].isSameNodeCaret(endCaret)) {
                return null;
            }
            depth += rval[1];
            return rval[0];
        }
    });
}
/**
 * Returns the Node sibling when this exists, otherwise the closest parent sibling. For example
 * R -> P -> T1, T2
 *   -> P2
 * returns T2 for node T1, P2 for node T2, and null for node P2.
 * @param node LexicalNode.
 * @returns An array (tuple) containing the found Lexical node and the depth difference, or null, if this node doesn't exist.
 */ function $getNextSiblingOrParentSibling(node) {
    const rval = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentSiblingOrParentSiblingCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(node, 'next'));
    return rval && [
        rval[0].origin,
        rval[1]
    ];
}
function $getDepth(node) {
    let depth = -1;
    for(let innerNode = node; innerNode !== null; innerNode = innerNode.getParent()){
        depth++;
    }
    return depth;
}
/**
 * Performs a right-to-left preorder tree traversal.
 * From the starting node it goes to the rightmost child, than backtracks to parent and finds new rightmost path.
 * It will return the next node in traversal sequence after the startingNode.
 * The traversal is similar to $dfs functions above, but the nodes are visited right-to-left, not left-to-right.
 * @param startingNode - The node to start the search.
 * @returns The next node in pre-order right to left traversal sequence or `null`, if the node does not exist
 */ function $getNextRightPreorderNode(startingNode) {
    const startCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaretOrSelf"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(startingNode, 'previous'));
    const next = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentSiblingOrParentSiblingCaret"])(startCaret, 'root');
    return next && next[0].origin;
}
/**
 * $dfs iterator (right to left). Tree traversal is done on the fly as new values are requested with O(1) memory.
 * @param startNode - The node to start the search, if omitted, it will start at the root node.
 * @param endNode - The node to end the search, if omitted, it will find all descendants of the startingNode.
 * @returns An iterator, each yielded value is a DFSNode. It will always return at least 1 node (the start node).
 */ function $reverseDfsIterator(startNode, endNode) {
    return $dfsCaretIterator('previous', startNode, endNode);
}
/**
 * Takes a node and traverses up its ancestors (toward the root node)
 * in order to find a specific type of node.
 * @param node - the node to begin searching.
 * @param klass - an instance of the type of node to look for.
 * @returns the node of type klass that was passed, or null if none exist.
 */ function $getNearestNodeOfType(node, klass) {
    let parent = node;
    while(parent != null){
        if (parent instanceof klass) {
            return parent;
        }
        parent = parent.getParent();
    }
    return null;
}
/**
 * Returns the element node of the nearest ancestor, otherwise throws an error.
 * @param startNode - The starting node of the search
 * @returns The ancestor node found
 */ function $getNearestBlockElementAncestorOrThrow(startNode) {
    const blockNode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(startNode, (node)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node) && !node.isInline());
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(blockNode)) {
        {
            formatDevErrorMessage(`Expected node ${startNode.__key} to have closest block element node.`);
        }
    }
    return blockNode;
}
/**
 * Attempts to resolve nested element nodes of the same type into a single node of that type.
 * It is generally used for marks/commenting
 * @param editor - The lexical editor
 * @param targetNode - The target for the nested element to be extracted from.
 * @param cloneNode - See {@link $createMarkNode}
 * @param handleOverlap - Handles any overlap between the node to extract and the targetNode
 * @returns The lexical editor
 */ function registerNestedElementResolver(editor, targetNode, cloneNode, handleOverlap) {
    const $isTargetNode = (node)=>{
        return node instanceof targetNode;
    };
    const $findMatch = (node)=>{
        // First validate we don't have any children that are of the target,
        // as we need to handle them first.
        const children = node.getChildren();
        for(let i = 0; i < children.length; i++){
            const child = children[i];
            if ($isTargetNode(child)) {
                return null;
            }
        }
        let parentNode = node;
        let childNode = node;
        while(parentNode !== null){
            childNode = parentNode;
            parentNode = parentNode.getParent();
            if ($isTargetNode(parentNode)) {
                return {
                    child: childNode,
                    parent: parentNode
                };
            }
        }
        return null;
    };
    const $elementNodeTransform = (node)=>{
        const match = $findMatch(node);
        if (match !== null) {
            const { child, parent } = match;
            // Simple path, we can move child out and siblings into a new parent.
            if (child.is(node)) {
                handleOverlap(parent, node);
                const nextSiblings = child.getNextSiblings();
                const nextSiblingsLength = nextSiblings.length;
                parent.insertAfter(child);
                if (nextSiblingsLength !== 0) {
                    const newParent = cloneNode(parent);
                    child.insertAfter(newParent);
                    for(let i = 0; i < nextSiblingsLength; i++){
                        newParent.append(nextSiblings[i]);
                    }
                }
                if (!parent.canBeEmpty() && parent.getChildrenSize() === 0) {
                    parent.remove();
                }
            }
        }
    };
    return editor.registerNodeTransform(targetNode, $elementNodeTransform);
}
/**
 * Clones the editor and marks it as dirty to be reconciled. If there was a selection,
 * it would be set back to its previous state, or null otherwise.
 * @param editor - The lexical editor
 * @param editorState - The editor's state
 */ function $restoreEditorState(editor, editorState) {
    const FULL_RECONCILE = 2;
    const nodeMap = new Map();
    const activeEditorState = editor._pendingEditorState;
    for (const [key, node] of editorState._nodeMap){
        nodeMap.set(key, (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$cloneWithProperties"])(node));
    }
    if (activeEditorState) {
        activeEditorState._nodeMap = nodeMap;
    }
    editor._dirtyType = FULL_RECONCILE;
    const selection = editorState._selection;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelection"])(selection === null ? null : selection.clone());
}
/**
 * If the selected insertion area is the root/shadow root node (see {@link lexical!$isRootOrShadowRoot}),
 * the node will be appended there, otherwise, it will be inserted before the insertion area.
 * If there is no selection where the node is to be inserted, it will be appended after any current nodes
 * within the tree, as a child of the root node. A paragraph will then be added after the inserted node and selected.
 * @param node - The node to be inserted
 * @returns The node after its insertion
 */ function $insertNodeToNearestRoot(node) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])() || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getPreviousSelection"])();
    let initialCaret;
    if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        initialCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$caretFromPoint"])(selection.focus, 'next');
    } else {
        if (selection != null) {
            const nodes = selection.getNodes();
            const lastNode = nodes[nodes.length - 1];
            if (lastNode) {
                initialCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(lastNode, 'next');
            }
        }
        initialCaret = initialCaret || (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getRoot"])(), 'previous').getFlipped().insert((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])());
    }
    const insertCaret = $insertNodeToNearestRootAtCaret(node, initialCaret);
    const adjacent = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getAdjacentChildCaret"])(insertCaret);
    const selectionCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isChildCaret"])(adjacent) ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$normalizeCaret"])(adjacent) : insertCaret;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setSelectionFromCaretRange"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getCollapsedCaretRange"])(selectionCaret));
    return node.getLatest();
}
/**
 * If the insertion caret is the root/shadow root node (see {@link lexical!$isRootOrShadowRoot}),
 * the node will be inserted there, otherwise the parent nodes will be split according to the
 * given options.
 * @param node - The node to be inserted
 * @param caret - The location to insert or split from
 * @returns The node after its insertion
 */ function $insertNodeToNearestRootAtCaret(node, caret, options) {
    let insertCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getCaretInDirection"])(caret, 'next');
    for(let nextCaret = insertCaret; nextCaret; nextCaret = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$splitAtPointCaretNext"])(nextCaret, options)){
        insertCaret = nextCaret;
    }
    if (!!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isTextPointCaret"])(insertCaret)) {
        formatDevErrorMessage(`$insertNodeToNearestRootAtCaret: An unattached TextNode can not be split`);
    }
    insertCaret.insert(node.isInline() ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$createParagraphNode"])().append(node) : node);
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getCaretInDirection"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(node.getLatest(), 'next'), caret.direction);
}
/**
 * Wraps the node into another node created from a createElementNode function, eg. $createParagraphNode
 * @param node - Node to be wrapped.
 * @param createElementNode - Creates a new lexical element to wrap the to-be-wrapped node and returns it.
 * @returns A new lexical element with the previous node appended within (as a child, including its children).
 */ function $wrapNodeInElement(node, createElementNode) {
    const elementNode = createElementNode();
    node.replace(elementNode);
    elementNode.append(node);
    return elementNode;
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
/**
 * @param object = The instance of the type
 * @param objectClass = The class of the type
 * @returns Whether the object is has the same Klass of the objectClass, ignoring the difference across window (e.g. different iframes)
 */ function objectKlassEquals(object, objectClass) {
    return object !== null ? Object.getPrototypeOf(object).constructor.name === objectClass.name : false;
}
/**
 * @deprecated Use Array filter or flatMap
 *
 * Filter the nodes
 * @param nodes Array of nodes that needs to be filtered
 * @param filterFn A filter function that returns node if the current node satisfies the condition otherwise null
 * @returns Array of filtered nodes
 */ function $filter(nodes, filterFn) {
    const result = [];
    for(let i = 0; i < nodes.length; i++){
        const node = filterFn(nodes[i]);
        if (node !== null) {
            result.push(node);
        }
    }
    return result;
}
/**
 * Applies the provided callback to each indentable block element in the Selection
 *
 * @param indentOrOutdent callback for performing the indent or outdent action
 * on a given block element.
 * @returns true if at least one block was handled, false otherwise.
 */ function $handleIndentAndOutdent(indentOrOutdent) {
    const selection = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSelection"])();
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isRangeSelection"])(selection)) {
        return false;
    }
    const alreadyHandled = new Set();
    const nodes = selection.getNodes();
    for(let i = 0; i < nodes.length; i++){
        const node = nodes[i];
        const key = node.getKey();
        if (alreadyHandled.has(key)) {
            continue;
        }
        const parentBlock = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$findMatchingParent"])(node, (parentNode)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(parentNode) && !parentNode.isInline());
        if (parentBlock === null) {
            continue;
        }
        const parentKey = parentBlock.getKey();
        if (parentBlock.canIndent() && !alreadyHandled.has(parentKey)) {
            alreadyHandled.add(parentKey);
            indentOrOutdent(parentBlock);
        }
    }
    return alreadyHandled.size > 0;
}
/**
 * Appends the node before the first child of the parent node
 * @param parent A parent node
 * @param node Node that needs to be appended
 */ function $insertFirst(parent, node) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(parent, 'next').insert(node);
}
let NEEDS_MANUAL_ZOOM = ("TURBOPACK compile-time truthy", 1) ? false : "TURBOPACK unreachable";
function needsManualZoom() {
    if (NEEDS_MANUAL_ZOOM === undefined) {
        // If the browser implements standardized CSS zoom, then the client rect
        // will be wider after zoom is applied
        // https://chromestatus.com/feature/5198254868529152
        // https://github.com/facebook/lexical/issues/6863
        const div = document.createElement('div');
        div.style.cssText = 'position: absolute; opacity: 0; width: 100px; left: -1000px;';
        document.body.appendChild(div);
        const noZoom = div.getBoundingClientRect();
        div.style.setProperty('zoom', '2');
        NEEDS_MANUAL_ZOOM = div.getBoundingClientRect().width === noZoom.width;
        document.body.removeChild(div);
    }
    return NEEDS_MANUAL_ZOOM;
}
/**
 * Calculates the zoom level of an element as a result of using
 * css zoom property. For browsers that implement standardized CSS
 * zoom (Firefox, Chrome >= 128), this will always return 1.
 * @param element
 * @param useManualZoom - If true, always use zoom level will be calculated manually, otherwise it will be calculated on as needed basis.
 */ function calculateZoomLevel(element, useManualZoom = false) {
    let zoom = 1;
    if (needsManualZoom() || useManualZoom) {
        while(element){
            zoom *= Number(window.getComputedStyle(element).getPropertyValue('zoom'));
            element = element.parentElement;
        }
    }
    return zoom;
}
/**
 * Checks if the editor is a nested editor created by LexicalNestedComposer
 */ function $isEditorIsNestedEditor(editor) {
    return editor._parentEditor !== null;
}
/**
 * A depth first last-to-first traversal of root that stops at each node that matches
 * $predicate and ensures that its parent is root. This is typically used to discard
 * invalid or unsupported wrapping nodes. For example, a TableNode must only have
 * TableRowNode as children, but an importer might add invalid nodes based on
 * caption, tbody, thead, etc. and this will unwrap and discard those.
 *
 * @param root The root to start the traversal
 * @param $predicate Should return true for nodes that are permitted to be children of root
 * @returns true if this unwrapped or removed any nodes
 */ function $unwrapAndFilterDescendants(root, $predicate) {
    return $unwrapAndFilterDescendantsImpl(root, $predicate, null);
}
function $unwrapAndFilterDescendantsImpl(root, $predicate, $onSuccess) {
    let didMutate = false;
    for (const node of $lastToFirstIterator(root)){
        if ($predicate(node)) {
            if ($onSuccess !== null) {
                $onSuccess(node);
            }
            continue;
        }
        didMutate = true;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(node)) {
            $unwrapAndFilterDescendantsImpl(node, $predicate, $onSuccess || ((child)=>node.insertAfter(child)));
        }
        node.remove();
    }
    return didMutate;
}
/**
 * A depth first traversal of the children array that stops at and collects
 * each node that `$predicate` matches. This is typically used to discard
 * invalid or unsupported wrapping nodes on a children array in the `after`
 * of an {@link lexical!DOMConversionOutput}. For example, a TableNode must only have
 * TableRowNode as children, but an importer might add invalid nodes based on
 * caption, tbody, thead, etc. and this will unwrap and discard those.
 *
 * This function is read-only and performs no mutation operations, which makes
 * it suitable for import and export purposes but likely not for any in-place
 * mutation. You should use {@link $unwrapAndFilterDescendants} for in-place
 * mutations such as node transforms.
 *
 * @param children The children to traverse
 * @param $predicate Should return true for nodes that are permitted to be children of root
 * @returns The children or their descendants that match $predicate
 */ function $descendantsMatching(children, $predicate) {
    const result = [];
    const stack = Array.from(children).reverse();
    for(let child = stack.pop(); child !== undefined; child = stack.pop()){
        if ($predicate(child)) {
            result.push(child);
        } else if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isElementNode"])(child)) {
            for (const grandchild of $lastToFirstIterator(child)){
                stack.push(grandchild);
            }
        }
    }
    return result;
}
/**
 * Return an iterator that yields each child of node from first to last, taking
 * care to preserve the next sibling before yielding the value in case the caller
 * removes the yielded node.
 *
 * @param node The node whose children to iterate
 * @returns An iterator of the node's children
 */ function $firstToLastIterator(node) {
    return $childIterator((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(node, 'next'));
}
/**
 * Return an iterator that yields each child of node from last to first, taking
 * care to preserve the previous sibling before yielding the value in case the caller
 * removes the yielded node.
 *
 * @param node The node whose children to iterate
 * @returns An iterator of the node's children
 */ function $lastToFirstIterator(node) {
    return $childIterator((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getChildCaret"])(node, 'previous'));
}
function $childIterator(startCaret) {
    const seen = new Set();
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["makeStepwiseIterator"])({
        hasNext: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$isSiblingCaret"],
        initial: startCaret.getAdjacentCaret(),
        map: (caret)=>{
            const origin = caret.origin.getLatest();
            if (seen !== null) {
                const key = origin.getKey();
                if (!!seen.has(key)) {
                    formatDevErrorMessage(`$childIterator: Cycle detected, node with key ${String(key)} has already been traversed`);
                }
                seen.add(key);
            }
            return origin;
        },
        step: (caret)=>caret.getAdjacentCaret()
    });
}
/**
 * Replace this node with its children
 *
 * @param node The ElementNode to unwrap and remove
 */ function $unwrapNode(node) {
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$rewindSiblingCaret"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getSiblingCaret"])(node, 'next')).splice(1, node.getChildren());
}
/**
 * A wrapper that creates bound functions and methods for the
 * StateConfig to save some boilerplate when defining methods
 * or exporting only the accessors from your modules rather
 * than exposing the StateConfig directly.
 */ /**
 * EXPERIMENTAL
 *
 * A convenience interface for working with {@link $getState} and
 * {@link $setState}.
 *
 * @param stateConfig The stateConfig to wrap with convenience functionality
 * @returns a StateWrapper
 */ function makeStateWrapper(stateConfig) {
    const $get = (node)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$getState"])(node, stateConfig);
    const $set = (node, valueOrUpdater)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$lexical$2f$Lexical$2e$dev$2e$mjs__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["$setState"])(node, stateConfig, valueOrUpdater);
    return {
        $get,
        $set,
        accessors: [
            $get,
            $set
        ],
        makeGetterMethod: ()=>function $getter() {
                return $get(this);
            },
        makeSetterMethod: ()=>function $setter(valueOrUpdater) {
                return $set(this, valueOrUpdater);
            },
        stateConfig
    };
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaDescription/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaDescriptionField",
    ()=>MetaDescriptionField
]);
const MetaDescriptionField = ({ hasGenerateFn = false, overrides })=>{
    return {
        name: 'description',
        type: 'textarea',
        admin: {
            components: {
                Field: {
                    clientProps: {
                        hasGenerateDescriptionFn: hasGenerateFn
                    },
                    path: '@payloadcms/plugin-seo/client#MetaDescriptionComponent'
                }
            }
        },
        localized: true,
        ...overrides ?? {}
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaImage/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaImageField",
    ()=>MetaImageField
]);
const MetaImageField = ({ hasGenerateFn = false, overrides, relationTo })=>{
    const imageField = {
        name: 'image',
        type: 'upload',
        admin: {
            components: {
                Field: {
                    clientProps: {
                        hasGenerateImageFn: hasGenerateFn
                    },
                    path: '@payloadcms/plugin-seo/client#MetaImageComponent'
                }
            },
            description: 'Maximum upload file size: 12MB. Recommended file size for images is <500KB.'
        },
        label: 'Meta Image',
        localized: true,
        relationTo,
        ...overrides ?? {}
    };
    return imageField;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaTitle/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MetaTitleField",
    ()=>MetaTitleField
]);
const MetaTitleField = ({ hasGenerateFn = false, overrides })=>{
    return {
        name: 'title',
        type: 'text',
        admin: {
            components: {
                Field: {
                    clientProps: {
                        hasGenerateTitleFn: hasGenerateFn
                    },
                    path: '@payloadcms/plugin-seo/client#MetaTitleComponent'
                }
            }
        },
        localized: true,
        ...overrides ?? {}
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Overview/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "OverviewField",
    ()=>OverviewField
]);
const OverviewField = ({ descriptionOverrides, descriptionPath, imagePath, overrides, titleOverrides, titlePath })=>{
    return {
        name: 'overview',
        type: 'ui',
        admin: {
            components: {
                Field: {
                    clientProps: {
                        descriptionOverrides,
                        descriptionPath,
                        imagePath,
                        titleOverrides,
                        titlePath
                    },
                    path: '@payloadcms/plugin-seo/client#OverviewComponent'
                }
            }
        },
        label: 'Overview',
        ...overrides ?? {}
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Preview/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "PreviewField",
    ()=>PreviewField
]);
const PreviewField = ({ descriptionPath, hasGenerateFn = false, overrides, titlePath })=>{
    return {
        name: 'preview',
        type: 'ui',
        admin: {
            components: {
                Field: {
                    clientProps: {
                        descriptionPath,
                        hasGenerateURLFn: hasGenerateFn,
                        titlePath
                    },
                    path: '@payloadcms/plugin-seo/client#PreviewComponent'
                }
            }
        },
        label: 'Preview',
        ...overrides ?? {}
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "seoPlugin",
    ()=>seoPlugin
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaDescription$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaDescription/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaImage$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaImage/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaTitle$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/MetaTitle/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Overview$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Overview/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Preview$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/fields/Preview/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/index.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
;
const seoPlugin = (pluginConfig)=>(config)=>{
        const defaultFields = [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Overview$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["OverviewField"])({}),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaTitle$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaTitleField"])({
                hasGenerateFn: typeof pluginConfig?.generateTitle === 'function'
            }),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaDescription$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaDescriptionField"])({
                hasGenerateFn: typeof pluginConfig?.generateDescription === 'function'
            }),
            ...pluginConfig?.uploadsCollection ? [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$MetaImage$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MetaImageField"])({
                    hasGenerateFn: typeof pluginConfig?.generateImage === 'function',
                    relationTo: pluginConfig.uploadsCollection
                })
            ] : [],
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$fields$2f$Preview$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["PreviewField"])({
                hasGenerateFn: typeof pluginConfig?.generateURL === 'function'
            })
        ];
        const seoFields = [
            {
                name: 'meta',
                type: 'group',
                fields: [
                    ...pluginConfig?.fields && typeof pluginConfig.fields === 'function' ? pluginConfig.fields({
                        defaultFields
                    }) : defaultFields
                ],
                interfaceName: pluginConfig.interfaceName,
                label: 'SEO'
            }
        ];
        return {
            ...config,
            collections: config.collections?.map((collection)=>{
                const { slug } = collection;
                const isEnabled = pluginConfig?.collections?.includes(slug);
                if (isEnabled) {
                    if (pluginConfig?.tabbedUI) {
                        // prevent issues with auth enabled collections having an email field that shouldn't be moved to the SEO tab
                        const emailField = collection.auth && !(typeof collection.auth === 'object' && collection.auth.disableLocalStrategy) && collection.fields?.find((field)=>'name' in field && field.name === 'email');
                        const hasOnlyEmailField = collection.fields?.length === 1 && emailField;
                        const seoTabs = hasOnlyEmailField ? [
                            {
                                type: 'tabs',
                                tabs: [
                                    {
                                        fields: seoFields,
                                        label: 'SEO'
                                    }
                                ]
                            }
                        ] : [
                            {
                                type: 'tabs',
                                tabs: [
                                    // append a new tab onto the end of the tabs array, if there is one at the first index
                                    // if needed, create a new `Content` tab in the first index for this collection's base fields
                                    ...collection?.fields?.[0]?.type === 'tabs' && collection?.fields?.[0]?.tabs ? collection.fields[0].tabs : [
                                        {
                                            fields: [
                                                ...emailField ? collection.fields.filter((field)=>'name' in field && field.name !== 'email') : collection.fields
                                            ],
                                            label: collection?.labels?.singular || 'Content'
                                        }
                                    ],
                                    {
                                        fields: seoFields,
                                        label: 'SEO'
                                    }
                                ]
                            }
                        ];
                        return {
                            ...collection,
                            fields: [
                                ...emailField ? [
                                    emailField
                                ] : [],
                                ...seoTabs,
                                ...collection?.fields?.[0]?.type === 'tabs' ? collection.fields.slice(1) : []
                            ]
                        };
                    }
                    return {
                        ...collection,
                        fields: [
                            ...collection?.fields || [],
                            ...seoFields
                        ]
                    };
                }
                return collection;
            }) || [],
            endpoints: [
                ...config.endpoints ?? [],
                {
                    handler: async (req)=>{
                        const data = await req.json?.();
                        const reqData = data ?? req.data;
                        const result = pluginConfig.generateTitle ? await pluginConfig.generateTitle({
                            ...data,
                            collectionConfig: config.collections?.find((c)=>c.slug === reqData.collectionSlug),
                            globalConfig: config.globals?.find((g)=>g.slug === reqData.globalSlug),
                            req
                        }) : '';
                        return new Response(JSON.stringify({
                            result
                        }), {
                            status: 200
                        });
                    },
                    method: 'post',
                    path: '/plugin-seo/generate-title'
                },
                {
                    handler: async (req)=>{
                        const data = await req.json?.();
                        const reqData = data ?? req.data;
                        const result = pluginConfig.generateDescription ? await pluginConfig.generateDescription({
                            ...data,
                            collectionConfig: config.collections?.find((c)=>c.slug === reqData.collectionSlug),
                            globalConfig: config.globals?.find((g)=>g.slug === reqData.globalSlug),
                            req
                        }) : '';
                        return new Response(JSON.stringify({
                            result
                        }), {
                            status: 200
                        });
                    },
                    method: 'post',
                    path: '/plugin-seo/generate-description'
                },
                {
                    handler: async (req)=>{
                        const data = await req.json?.();
                        const reqData = data ?? req.data;
                        const result = pluginConfig.generateURL ? await pluginConfig.generateURL({
                            ...data,
                            collectionConfig: config.collections?.find((c)=>c.slug === reqData.collectionSlug),
                            globalConfig: config.globals?.find((g)=>g.slug === reqData.globalSlug),
                            req
                        }) : '';
                        return new Response(JSON.stringify({
                            result
                        }), {
                            status: 200
                        });
                    },
                    method: 'post',
                    path: '/plugin-seo/generate-url'
                },
                {
                    handler: async (req)=>{
                        const data = await req.json?.();
                        const reqData = data ?? req.data;
                        const result = pluginConfig.generateImage ? await pluginConfig.generateImage({
                            ...data,
                            collectionConfig: config.collections?.find((c)=>c.slug === reqData.collectionSlug),
                            globalConfig: config.globals?.find((g)=>g.slug === reqData.globalSlug),
                            req
                        }) : '';
                        return new Response(JSON.stringify({
                            result
                        }), {
                            status: 200
                        });
                    },
                    method: 'post',
                    path: '/plugin-seo/generate-image'
                }
            ],
            globals: config.globals?.map((global)=>{
                const { slug } = global;
                const isEnabled = pluginConfig?.globals?.includes(slug);
                if (isEnabled) {
                    if (pluginConfig?.tabbedUI) {
                        const seoTabs = [
                            {
                                type: 'tabs',
                                tabs: [
                                    // append a new tab onto the end of the tabs array, if there is one at the first index
                                    // if needed, create a new `Content` tab in the first index for this global's base fields
                                    ...global?.fields?.[0]?.type === 'tabs' && global?.fields?.[0].tabs ? global.fields[0].tabs : [
                                        {
                                            fields: [
                                                ...global?.fields || []
                                            ],
                                            label: global?.label || 'Content'
                                        }
                                    ],
                                    {
                                        fields: seoFields,
                                        label: 'SEO'
                                    }
                                ]
                            }
                        ];
                        return {
                            ...global,
                            fields: [
                                ...seoTabs,
                                ...global?.fields?.[0]?.type === 'tabs' ? global.fields.slice(1) : []
                            ]
                        };
                    }
                    return {
                        ...global,
                        fields: [
                            ...global?.fields || [],
                            ...seoFields
                        ]
                    };
                }
                return global;
            }) || [],
            i18n: {
                ...config.i18n,
                translations: (0, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__["deepMergeSimple"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["translations"], config.i18n?.translations ?? {})
            }
        };
    };
__turbopack_async_result__();
} catch(e) { __turbopack_async_result__(e); } }, false);}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ar.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ar",
    ()=>ar
]);
const ar = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'قريبًا',
        autoGenerate: 'توليد تلقائي',
        bestPractices: 'أفضل الممارسات',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} أحرف، ',
        charactersLeftOver: '{{characters}} متبقية',
        charactersToGo: '{{characters}} للمضي قدمًا',
        charactersTooMany: '{{characters}} أكثر من اللازم',
        checksPassing: '{{current}}/{{max}} التحقق تم بنجاح',
        good: 'جيد',
        imageAutoGenerationTip: 'سيقوم التوليد التلقائي باسترجاع الصورة الرئيسية المحددة.',
        lengthTipDescription: 'يجب أن يتراوح هذا بين {{minLength}} و{{maxLength}} حرفًا. للحصول على مساعدة في كتابة أوصاف ميتا ذات جودة، راجع ',
        lengthTipTitle: 'يجب أن يتراوح هذا بين {{minLength}} و{{maxLength}} حرفًا. للحصول على مساعدة في كتابة عناوين ميتا ذات جودة، راجع ',
        missing: 'مفقود',
        noImage: 'لا توجد صورة',
        preview: 'معاينة',
        previewDescription: 'قد تختلف النتائج الدقيقة بناءً على المحتوى وملاءمة البحث.',
        tooLong: 'طويل جدًا',
        tooShort: 'قصير جدًا'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/az.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "az",
    ()=>az
]);
const az = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Demək olar ki, çatdıq',
        autoGenerate: 'Avtomatik yaradılacaq',
        bestPractices: 'ən yaxşı təcrübələr',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} simvol, ',
        charactersLeftOver: '{{characters}} qalan',
        charactersToGo: '{{characters}} qalan',
        charactersTooMany: '{{characters}} çox',
        checksPassing: '{{current}}/{{max}} yoxlamalar uğurla keçdi',
        good: 'Yaxşı',
        imageAutoGenerationTip: 'Avtomatik yaradılma seçilən başlıq şəkilini əldə edəcək.',
        lengthTipDescription: 'Bu, {{minLength}} ilə {{maxLength}} simvol arasında olmalıdır. Keyfiyyətli meta təsvirləri yazmaq üçün kömək üçün baxın ',
        lengthTipTitle: 'Bu, {{minLength}} ilə {{maxLength}} simvol arasında olmalıdır. Keyfiyyətli meta başlıqları yazmaq üçün kömək üçün baxın ',
        missing: 'Yoxdur',
        noImage: 'Şəkil yoxdur',
        preview: 'Önizləmə',
        previewDescription: 'Dəqiq nəticələr, məzmun və axtarış uyğunluğuna görə dəyişə bilər.',
        tooLong: 'Çox uzun',
        tooShort: 'Çox qısa'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/bg.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "bg",
    ()=>bg
]);
const bg = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Почти стигнахме',
        autoGenerate: 'Автоматично генериране',
        bestPractices: 'най-добри практики',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} знака, ',
        charactersLeftOver: '{{characters}} оставащи',
        charactersToGo: '{{characters}} за въвеждане',
        charactersTooMany: '{{characters}} твърде много',
        checksPassing: '{{current}}/{{max}} проверки преминали успешно',
        good: 'Добре',
        imageAutoGenerationTip: 'Автоматичното генериране ще извлече избраното основно изображение.',
        lengthTipDescription: 'Това трябва да бъде между {{minLength}} и {{maxLength}} знака. За помощ при писането на качествени мета описания, вижте ',
        lengthTipTitle: 'Това трябва да бъде между {{minLength}} и {{maxLength}} знака. За помощ при писането на качествени мета заглавия, вижте ',
        missing: 'Липсва',
        noImage: 'Няма изображение',
        preview: 'Предварителен преглед',
        previewDescription: 'Точните резултати може да варират в зависимост от съдържанието и релевантността на търсенето.',
        tooLong: 'Твърде дълго',
        tooShort: 'Твърде късо'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ca.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ca",
    ()=>ca
]);
const ca = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Quasi hi som',
        autoGenerate: 'Generar automàticament',
        bestPractices: 'bones pràctiques',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caràcters, ',
        charactersLeftOver: '{{characters}} restants',
        charactersToGo: '{{characters}} per escriure',
        charactersTooMany: '{{characters}} massa',
        checksPassing: '{{current}}/{{max}} comprovacions aprovades',
        good: 'Bé',
        imageAutoGenerationTip: 'La generació automàtica recuperarà la imatge destacada seleccionada.',
        lengthTipDescription: 'Això hauria de ser entre {{minLength}} i {{maxLength}} caràcters. Per obtenir ajuda per escriure descripcions meta de qualitat, consulta ',
        lengthTipTitle: 'Això hauria de ser entre {{minLength}} i {{maxLength}} caràcters. Per obtenir ajuda per escriure títols meta de qualitat, consulta ',
        missing: 'Falta',
        noImage: 'Sense imatge',
        preview: 'Previsualització',
        previewDescription: 'Els resultats exactes poden variar segons el contingut i la rellevància de la cerca.',
        tooLong: 'Massa llarg',
        tooShort: 'Massa curt'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/cs.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "cs",
    ()=>cs
]);
const cs = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Skoro hotovo',
        autoGenerate: 'Generovat automaticky',
        bestPractices: 'osvědčené postupy',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} znaků, ',
        charactersLeftOver: '{{characters}} zbývá',
        charactersToGo: '{{characters}} zbývá',
        charactersTooMany: '{{characters}} navíc',
        checksPassing: '{{current}}/{{max}} kontrol úspěšně splněno',
        good: 'Dobré',
        imageAutoGenerationTip: 'Automatická generace načte vybraný hero obrázek.',
        lengthTipDescription: 'Toto by mělo mít mezi {{minLength}} a {{maxLength}} znaky. Pomoc při psaní kvalitních meta popisů navštivte ',
        lengthTipTitle: 'Toto by mělo mít mezi {{minLength}} a {{maxLength}} znaky. Pomoc při psaní kvalitních meta titulů navštivte ',
        missing: 'Chybí',
        noImage: 'Bez obrázku',
        preview: 'Náhled',
        previewDescription: 'Přesný výsledek se může lišit v závislosti na obsahu a relevanci vyhledávání.',
        tooLong: 'Příliš dlouhé',
        tooShort: 'Příliš krátké'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/da.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "da",
    ()=>da
]);
const da = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Næsten der',
        autoGenerate: 'Automatisk generering',
        bestPractices: 'bedste praksis',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} tegn, ',
        charactersLeftOver: '{{characters}} tilbage',
        charactersToGo: '{{characters}} tilbage at skrive',
        charactersTooMany: '{{characters}} for mange',
        checksPassing: '{{current}}/{{max}} kontroller er bestået',
        good: 'God',
        imageAutoGenerationTip: 'Automatisk generering vil hente det valgte hero-billede.',
        lengthTipDescription: 'Dette bør være mellem {{minLength}} og {{maxLength}} tegn. For hjælp til at skrive kvalitetsmeta-beskrivelser, se ',
        lengthTipTitle: 'Dette bør være mellem {{minLength}} og {{maxLength}} tegn. For hjælp til at skrive kvalitetsmeta-titler, se ',
        missing: 'Manglende',
        noImage: 'Ingen billede',
        preview: 'Forhåndsvisning',
        previewDescription: 'De præcise resultater kan variere afhængigt af indhold og søge relevans.',
        tooLong: 'For lang',
        tooShort: 'For kort'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/de.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "de",
    ()=>de
]);
const de = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Fast da',
        autoGenerate: 'Automatisch generieren',
        bestPractices: 'Best Practices',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} Zeichen, ',
        charactersLeftOver: '{{characters}} verbleiben',
        charactersToGo: '{{characters}} übrig',
        charactersTooMany: '{{characters}} zu viel',
        checksPassing: '{{current}}/{{max}} Kontrollen erfolgreich',
        good: 'Gut',
        imageAutoGenerationTip: 'Die automatische Generierung ruft das ausgewählte Hauptbild ab.',
        lengthTipDescription: 'Diese sollte zwischen {{minLength}} und {{maxLength}} Zeichen lang sein. Für Hilfe beim Schreiben von qualitativ hochwertigen Meta-Beschreibungen siehe ',
        lengthTipTitle: 'Dieser sollte zwischen {{minLength}} und {{maxLength}} Zeichen lang sein. Für Hilfe beim Schreiben von qualitativ hochwertigen Meta-Titeln siehe ',
        missing: 'Fehlt',
        noImage: 'Kein Bild',
        preview: 'Vorschau',
        previewDescription: 'Die genauen Ergebnislisten können je nach Inhalt und Suchrelevanz variieren.',
        tooLong: 'Zu lang',
        tooShort: 'Zu kurz'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/en.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "en",
    ()=>en
]);
const en = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Almost there',
        autoGenerate: 'Auto-generate',
        bestPractices: 'best practices',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} chars, ',
        charactersLeftOver: '{{characters}} left over',
        charactersToGo: '{{characters}} to go',
        charactersTooMany: '{{characters}} too many',
        checksPassing: '{{current}}/{{max}} checks are passing',
        good: 'Good',
        imageAutoGenerationTip: 'Auto-generation will retrieve the selected hero image.',
        lengthTipDescription: 'This should be between {{minLength}} and {{maxLength}} characters. For help in writing quality meta descriptions, see ',
        lengthTipTitle: 'This should be between {{minLength}} and {{maxLength}} characters. For help in writing quality meta titles, see ',
        missing: 'Missing',
        noImage: 'No image',
        preview: 'Preview',
        previewDescription: 'Exact result listings may vary based on content and search relevancy.',
        tooLong: 'Too long',
        tooShort: 'Too short'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/es.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "es",
    ()=>es
]);
const es = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Ya casi está',
        autoGenerate: 'Generar automáticamente',
        bestPractices: 'Mejores prácticas',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caracteres, ',
        charactersLeftOver: '{{characters}} restantes',
        charactersToGo: '{{characters}} por completar',
        charactersTooMany: '{{characters}} de más',
        checksPassing: '{{current}}/{{max}} comprobaciones correctas',
        good: 'Bien',
        imageAutoGenerationTip: 'La generación automática recuperará la imagen de héroe seleccionada',
        lengthTipDescription: 'Debe tener entre {{minLength}} y {{maxLength}} caracteres. Para obtener ayuda sobre cómo escribir meta descripciones de calidad, consulte ',
        lengthTipTitle: 'Debe tener entre {{minLength}} y {{maxLength}} caracteres. Para obtener ayuda sobre cómo escribir meta títulos de calidad, consulte ',
        missing: 'Faltante',
        noImage: 'Sin imagen',
        preview: 'Vista previa',
        previewDescription: 'Las resultados exactos pueden variar en función del contenido y la relevancia de la búsqueda.',
        tooLong: 'Demasiado largo',
        tooShort: 'Demasiado corto'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/et.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "et",
    ()=>et
]);
const et = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Peaaegu kohal',
        autoGenerate: 'Automaatne genereerimine',
        bestPractices: 'parimad tavad',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} tähemärki, ',
        charactersLeftOver: '{{characters}} alles',
        charactersToGo: '{{characters}} kirjutada',
        charactersTooMany: '{{characters}} liiga palju',
        checksPassing: '{{current}}/{{max}} kontrolli on läbitud',
        good: 'Hea',
        imageAutoGenerationTip: 'Automaatne genereerimine toob valitud kangelaspildi.',
        lengthTipDescription: 'See peaks olema vahemikus {{minLength}} ja {{maxLength}} tähemärki. Kvaliteetsete meta-kirjelduste kirjutamiseks vaata ',
        lengthTipTitle: 'See peaks olema vahemikus {{minLength}} ja {{maxLength}} tähemärki. Kvaliteetsete meta-pealkirjade kirjutamiseks vaata ',
        missing: 'Puudub',
        noImage: 'Pilt puudub',
        preview: 'Eelvaade',
        previewDescription: 'Täpsed tulemused võivad varieeruda sõltuvalt sisust ja otsingu asjakohasusest.',
        tooLong: 'Liiga pikk',
        tooShort: 'Liiga lühike'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/fa.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "fa",
    ()=>fa
]);
const fa = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'چیزیی باقی نمونده',
        autoGenerate: 'تولید خودکار',
        bestPractices: 'آموزش بیشتر',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} کلمه، ',
        charactersLeftOver: '{{characters}} باقی مانده',
        charactersToGo: '{{characters}} باقی مانده',
        charactersTooMany: '{{characters}} بیش از حد',
        checksPassing: '{{current}}/{{max}} بررسی‌ها با موفقیت انجام شده است',
        good: 'خوب',
        imageAutoGenerationTip: 'این قابلیت، تصویر فعلی بارگذاری شده در مجموعه محتوای شما را بازیابی می‌کند',
        lengthTipDescription: 'این باید بین {{minLength}} و {{maxLength}} کلمه باشد. برای کمک در نوشتن توضیحات متا با کیفیت، مراجعه کنید به ',
        lengthTipTitle: 'این باید بین {{minLength}} و {{maxLength}} کلمه باشد. برای کمک در نوشتن عناوین متا با کیفیت، مراجعه کنید به ',
        missing: 'ناقص',
        noImage: 'بدون تصویر',
        preview: 'پیش‌نمایش',
        previewDescription: 'فهرست نتایج ممکن است بر اساس محتوا و متناسب با کلمه کلیدی جستجو شده باشند',
        tooLong: 'خیلی طولانی',
        tooShort: 'خیلی کوتاه'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/fr.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "fr",
    ()=>fr
]);
const fr = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'On y est presque',
        autoGenerate: 'Auto-générer',
        bestPractices: 'bonnes pratiques',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caractères, ',
        charactersLeftOver: '{{characters}} restants',
        charactersToGo: '{{characters}} à ajouter',
        charactersTooMany: '{{characters}} en trop',
        checksPassing: '{{current}}/{{max}} vérifications réussies',
        good: 'Bien',
        imageAutoGenerationTip: "L'auto-génération récupérera l'image principale sélectionnée.",
        lengthTipDescription: "Ceci devrait contenir entre {{minLength}} et {{maxLength}} caractères. Pour obtenir de l'aide pour rédiger des descriptions meta de qualité, consultez les ",
        lengthTipTitle: "Ceci devrait contenir entre {{minLength}} et {{maxLength}} caractères. Pour obtenir de l'aide pour rédiger des titres meta de qualité, consultez les ",
        missing: 'Manquant',
        noImage: "Pas d'image",
        preview: 'Aperçu',
        previewDescription: 'Les résultats exacts peuvent varier en fonction du contenu et de la pertinence de la recherche.',
        tooLong: 'Trop long',
        tooShort: 'Trop court'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/he.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "he",
    ()=>he
]);
const he = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'כמעט שם',
        autoGenerate: 'הפקה אוטומטית',
        bestPractices: 'הצעות טובות',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} תו, ',
        charactersLeftOver: '{{characters}} נותרו',
        charactersToGo: '{{characters}} להקליד',
        charactersTooMany: '{{characters}} יותר מידי',
        checksPassing: '{{current}}/{{max}} בדיקות עברו בהצלחה',
        good: 'טוב',
        imageAutoGenerationTip: 'ההפקה האוטומטית תמשוך את התמונה הראשית שנבחרה.',
        lengthTipDescription: 'זה צריך להיות בין {{minLength}} ו{{maxLength}} תו. לעזרה בכתיבת תיאורי מטא איכותיים, עיין ב-',
        lengthTipTitle: 'זה צריך להיות בין {{minLength}} ו{{maxLength}} תו. לעזרה בכתיבת כותרות מטא איכותיות, עיין ב-',
        missing: 'חסר',
        noImage: 'אין תמונה',
        preview: 'תצוגה מקדימה',
        previewDescription: 'תוצאות מדויקות עשויות להשתנות בהתאם לתוכן ולרלוונטיות של החיפוש.',
        tooLong: 'ארוך מידי',
        tooShort: 'קצר מידי'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hr.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hr",
    ()=>hr
]);
const hr = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Gotovi smo skoro',
        autoGenerate: 'Automatsko generiranje',
        bestPractices: 'najbolje prakse',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} znakova, ',
        charactersLeftOver: '{{characters}} preostalo',
        charactersToGo: '{{characters}} preostalo za unijeti',
        charactersTooMany: '{{characters}} previše',
        checksPassing: '{{current}}/{{max}} provjera prošlo',
        good: 'Dobro',
        imageAutoGenerationTip: 'Automatsko generiranje će preuzeti odabranu sliku heroja.',
        lengthTipDescription: 'Ovo bi trebalo biti između {{minLength}} i {{maxLength}} znakova. Za pomoć u pisanju kvalitetnih meta opisa, pogledajte ',
        lengthTipTitle: 'Ovo bi trebalo biti između {{minLength}} i {{maxLength}} znakova. Za pomoć u pisanju kvalitetnih meta naslova, pogledajte ',
        missing: 'Nedostaje',
        noImage: 'Nema slike',
        preview: 'Pregled',
        previewDescription: 'Točni rezultati mogu varirati ovisno o sadržaju i relevantnosti pretrage.',
        tooLong: 'Predugačko',
        tooShort: 'Prekratko'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hu.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hu",
    ()=>hu
]);
const hu = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Majdnem kész',
        autoGenerate: 'Automatikus generálás',
        bestPractices: 'legjobb gyakorlatok',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} karakter, ',
        charactersLeftOver: '{{characters}} hátra van',
        charactersToGo: '{{characters}} hátra van a beíráshoz',
        charactersTooMany: '{{characters}} túl sok',
        checksPassing: '{{current}}/{{max}} ellenőrzés sikeres',
        good: 'Jó',
        imageAutoGenerationTip: 'Az automatikus generálás a kiválasztott hős képet fogja lekérni.',
        lengthTipDescription: 'Ez legyen {{minLength}} és {{maxLength}} karakter között. Segítség a minőségi meta leírások írásához, nézd meg ',
        lengthTipTitle: 'Ez legyen {{minLength}} és {{maxLength}} karakter között. Segítség a minőségi meta címek írásához, nézd meg ',
        missing: 'Hiányzik',
        noImage: 'Nincs kép',
        preview: 'Előnézet',
        previewDescription: 'A pontos eredmények változhatnak a tartalom és a keresési relevancia alapján.',
        tooLong: 'Túl hosszú',
        tooShort: 'Túl rövid'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hy.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hy",
    ()=>hy
]);
const hy = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Գրեթե պատրաստ է',
        autoGenerate: 'Ինքնաշարժ գեներացիա',
        bestPractices: 'լավագույն փորձեր',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} նիշ, ',
        charactersLeftOver: '{{characters}} նիշ ավել է մնացել',
        charactersToGo: '{{characters}} նիշ մնացել է',
        charactersTooMany: '{{characters}} նիշ չափազանց շատ է',
        checksPassing: '{{current}}/{{max}} ստուգումները հաջող են անցել',
        good: 'Լավ',
        imageAutoGenerationTip: 'Ինքնաշարժ գեներացիան կվերցնի ընտրված հերոս նկարը։',
        lengthTipDescription: 'Սա պետք է լինի {{minLength}}-ից {{maxLength}} նիշի սահմաններում։ Որակյալ մետա նկարագրություններ գրելու համար տես ',
        lengthTipTitle: 'Սա պետք է լինի {{minLength}}-ից {{maxLength}} նիշի սահմաններում։ Որակյալ մետա վերնագրեր գրելու համար տես ',
        missing: 'Բացակայում է',
        noImage: 'Նկար չկա',
        preview: 'Նախադիտում',
        previewDescription: 'Իրական արդյունքների ցուցադրումը կարող է տարբեր լինել՝ բովանդակության և որոնման համապատասխանության հիման վրա։',
        tooLong: 'Չափազանց երկար է',
        tooShort: 'Չափազանց կարճ է'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "translations",
    ()=>translations
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ar$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ar.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$az$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/az.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$bg$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/bg.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ca$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ca.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$cs$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/cs.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$da$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/da.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$de$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/de.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$en$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/en.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$es$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/es.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$et$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/et.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$fa$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/fa.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$fr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/fr.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$he$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/he.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hr.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hu$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hu.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hy$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/hy.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$is$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/is.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$it$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/it.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ja$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ja.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ko$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ko.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$lt$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/lt.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$my$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/my.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$nb$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/nb.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$nl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/nl.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$pl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/pl.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$pt$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/pt.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ro$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ro.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$rs$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/rs.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$rsLatin$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/rsLatin.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ru$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ru.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sk$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sk.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sl.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sv$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sv.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ta.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$th$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/th.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$tr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/tr.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$uk$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/uk.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$vi$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/vi.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$zh$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/zh.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$zhTw$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/zhTw.js [app-rsc] (ecmascript)");
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
;
;
;
;
const translations = {
    ar: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ar$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ar"],
    az: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$az$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["az"],
    bg: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$bg$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["bg"],
    ca: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ca$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ca"],
    cs: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$cs$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["cs"],
    da: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$da$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["da"],
    de: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$de$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["de"],
    en: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$en$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["en"],
    es: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$es$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["es"],
    et: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$et$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["et"],
    fa: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$fa$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["fa"],
    fr: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$fr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["fr"],
    he: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$he$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["he"],
    hr: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hr"],
    hu: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hu$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hu"],
    hy: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$hy$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hy"],
    is: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$is$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["is"],
    it: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$it$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["it"],
    ja: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ja$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ja"],
    ko: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ko$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ko"],
    lt: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$lt$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["lt"],
    my: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$my$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["my"],
    nb: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$nb$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["nb"],
    nl: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$nl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["nl"],
    pl: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$pl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["pl"],
    pt: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$pt$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["pt"],
    ro: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ro$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ro"],
    rs: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$rs$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["rs"],
    'rs-latin': __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$rsLatin$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["rsLatin"],
    ru: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ru$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ru"],
    sk: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sk$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["sk"],
    sl: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sl$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["sl"],
    sv: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$sv$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["sv"],
    ta: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$ta$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["ta"],
    th: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$th$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["th"],
    tr: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$tr$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["tr"],
    uk: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$uk$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["uk"],
    vi: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$vi$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["vi"],
    zh: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$zh$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["zh"],
    'zh-TW': __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$plugin$2d$seo$2f$dist$2f$translations$2f$zhTw$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["zhTw"]
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/is.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "is",
    ()=>is
]);
const is = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Næstum komið',
        autoGenerate: 'Mynda sjálfkrafa',
        bestPractices: 'bestu venjur',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} stafir, ',
        charactersLeftOver: '{{characters}} eftir',
        charactersToGo: '{{characters}} eftir',
        charactersTooMany: '{{characters}} of mikið',
        checksPassing: '{{current}}/{{max}} athuganir standast',
        good: 'Gott',
        imageAutoGenerationTip: 'Sjálfvirk myndun mun sækja valda hetjumynd.',
        lengthTipDescription: 'Þetta ætti að vera á milli {{minLength}} og {{maxLength}} stafir. Fyrir hjálp með að skrifa góða lýsingu, sjáðu ',
        lengthTipTitle: 'Þetta ætti að vera á milli {{minLength}} og {{maxLength}} stafir. Fyrir hjálp með að skrifa góðan titil, sjáðu ',
        missing: 'Vantar',
        noImage: 'Engin mynd',
        preview: 'Forskoðun',
        previewDescription: 'Nákvæmar niðurstöður geta verið mismunandi eftir efni og viðeigandi leitar.',
        tooLong: 'Of langt',
        tooShort: 'Of stutt'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/it.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "it",
    ()=>it
]);
const it = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Ci siamo quasi',
        autoGenerate: 'Generazione automatica',
        bestPractices: 'migliori pratiche',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caratteri, ',
        charactersLeftOver: '{{characters}} rimasti',
        charactersToGo: '{{characters}} mancanti',
        charactersTooMany: '{{characters}} in più',
        checksPassing: '{{current}}/{{max}} controlli superati',
        good: 'Bene',
        imageAutoGenerationTip: "La generazione automatica recupererà l'immagine selezionata per l'hero",
        lengthTipDescription: 'Dovrebbe essere compreso tra {{minLength}} e {{maxLength}} caratteri. Per assistenza nella scrittura di meta descrizioni di qualità, vedere ',
        lengthTipTitle: 'Dovrebbe essere compreso tra {{minLength}} e {{maxLength}} caratteri. Per assistenza nella scrittura di meta titoli di qualità, vedere ',
        missing: 'Mancante',
        noImage: 'Nessuna Immagine',
        preview: 'Anteprima',
        previewDescription: 'I risultati esatti possono variare in base al contenuto e alla pertinenza della ricerca.',
        tooLong: 'Troppo lungo',
        tooShort: 'Troppo corto'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ja.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ja",
    ()=>ja
]);
const ja = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'もう少しで完了',
        autoGenerate: '自動生成',
        bestPractices: 'ベストプラクティス',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} 文字, ',
        charactersLeftOver: '{{characters}} 文字残り',
        charactersToGo: '{{characters}} 文字入力する必要があります',
        charactersTooMany: '{{characters}} 文字多すぎ',
        checksPassing: '{{current}}/{{max}} のチェックが合格しています',
        good: '良い',
        imageAutoGenerationTip: '自動生成は、選択されたヒーロー画像を取得します。',
        lengthTipDescription: 'これは {{minLength}} と {{maxLength}} 文字の間である必要があります。質の高いメタディスクリプションを書くためのヘルプについては、こちらを参照してください ',
        lengthTipTitle: 'これは {{minLength}} と {{maxLength}} 文字の間である必要があります。質の高いメタタイトルを書くためのヘルプについては、こちらを参照してください ',
        missing: '不足',
        noImage: '画像なし',
        preview: 'プレビュー',
        previewDescription: '正確な結果は、コンテンツおよび検索の関連性に基づいて異なる場合があります。',
        tooLong: '長すぎる',
        tooShort: '短すぎる'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ko.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ko",
    ()=>ko
]);
const ko = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: '거의 완료',
        autoGenerate: '자동 생성',
        bestPractices: '모범 사례',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} 자, ',
        charactersLeftOver: '{{characters}} 자 초과',
        charactersToGo: '{{characters}} 자 남음',
        charactersTooMany: '{{characters}} 자 초과',
        checksPassing: '{{current}}/{{max}}개의 검사를 통과했습니다',
        good: '좋음',
        imageAutoGenerationTip: '자동 생성은 선택한 대표 이미지를 가져옵니다.',
        lengthTipDescription: '이 값은 {{minLength}}자에서 {{maxLength}}자 사이여야 합니다. 품질 높은 메타 설명 작성에 대한 도움말은 ',
        lengthTipTitle: '이 값은 {{minLength}}자에서 {{maxLength}}자 사이여야 합니다. 품질 높은 메타 제목 작성에 대한 도움말은 ',
        missing: '누락됨',
        noImage: '이미지 없음',
        preview: '미리 보기',
        previewDescription: '정확한 검색 결과 목록은 콘텐츠 및 검색 적합성에 따라 달라질 수 있습니다.',
        tooLong: '너무 김',
        tooShort: '너무 짧음'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/lt.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "lt",
    ()=>lt
]);
const lt = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Beveik baigta',
        autoGenerate: 'Automatinis generavimas',
        bestPractices: 'geriausios praktikos',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} simbolių, ',
        charactersLeftOver: '{{characters}} likusių simbolių',
        charactersToGo: '{{characters}} simbolių liko',
        charactersTooMany: '{{characters}} per daug simbolių',
        checksPassing: '{{current}}/{{max}} tikrinimų sėkmingi',
        good: 'Gerai',
        imageAutoGenerationTip: 'Automatinis generavimas paims pasirinktą pagrindinį vaizdą.',
        lengthTipDescription: 'Šis tekstas turi būti tarp {{minLength}} ir {{maxLength}} simbolių. Norėdami gauti pagalbos rašant kokybiškus meta aprašus, žiūrėkite ',
        lengthTipTitle: 'Šis tekstas turi būti tarp {{minLength}} ir {{maxLength}} simbolių. Norėdami gauti pagalbos rašant kokybiškus meta pavadinimus, žiūrėkite ',
        missing: 'Trūksta',
        noImage: 'Nėra vaizdo',
        preview: 'Peržiūra',
        previewDescription: 'Tikrųjų paieškos rezultatų gali skirtis priklausomai nuo turinio ir paieškos svarbos.',
        tooLong: 'Per ilgas',
        tooShort: 'Per trumpas'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/my.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "my",
    ()=>my
]);
const my = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'နည်းနည်းပဲကျန်သေးသည်',
        autoGenerate: 'အလိုအလျောက်ထုတ်လုပ်မည်',
        bestPractices: 'အကောင်းဆုံးအကဲဖြတ်မှုများ',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} လုံး, ',
        charactersLeftOver: '{{characters}} လုံးကျော်နေသည်',
        charactersToGo: '{{characters}} လုံးလိုသေးသည်',
        charactersTooMany: '{{characters}} လုံးများသွားသည်',
        checksPassing: '{{current}}/{{max}} စစ်ဆေးမှုအောင်မြင်ခဲ့သည်',
        good: 'ကောင်းမွန်သည်',
        imageAutoGenerationTip: 'အလိုအလျောက်ထုတ်လုပ်မှုသည် ရွေးချယ်ထားသော ဟီးရိုးပုံကိုယူမည်။',
        lengthTipDescription: 'ဤအကြောင်းအရာသည် {{minLength}} နှင့် {{maxLength}} အကြားရှိသင့်သည်။ အရည်အသွေးမြင့် meta ဖော်ပြချက်ရေးသားရန်အတွက်အကြံဉာဏ်များကို ကြည့်ရန် ',
        lengthTipTitle: 'ဤအကြောင်းအရာသည် {{minLength}} နှင့် {{maxLength}} အကြားရှိသင့်သည်။ အရည်အသွေးမြင့် meta ခေါင်းစဉ်ရေးသားရန်အတွက်အကြံဉာဏ်များကို ကြည့်ရန် ',
        missing: 'ပျောက်နေသည်',
        noImage: 'ပုံမရှိပါ',
        preview: 'မကြိုတင်ကြည့်ရှုနိုင်ပါ',
        previewDescription: 'တိကျသော ရှာဖွေမှုရလဒ်များသည် အကြောင်းအရာနှင့် ရှာဖွေရေးအသင့်တော်မှုပေါ်မူတည်၍ မတူကွဲပြားနိုင်သည်။',
        tooLong: 'တော်တော်ကြာသည်',
        tooShort: 'တော်တော်တိုသည်'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/nb.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "nb",
    ()=>nb
]);
const nb = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Nesten der',
        autoGenerate: 'Auto-generer',
        bestPractices: 'beste praksis',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} tegn, ',
        charactersLeftOver: '{{characters}} til overs',
        charactersToGo: '{{characters}} igjen',
        charactersTooMany: '{{characters}} for mange',
        checksPassing: '{{current}}/{{max}} sjekker bestått',
        good: 'Bra',
        imageAutoGenerationTip: 'Auto-generering vil hente det valgte hero-bildet.',
        lengthTipDescription: 'Dette bør være mellom {{minLength}} og {{maxLength}} tegn. For hjelp til å skrive beskrivelser av god kvalitet, se ',
        lengthTipTitle: 'Dette bør være mellom {{minLength}} og {{maxLength}} tegn. For hjelp til å skrive metatitler av god kvalitet, se ',
        missing: 'Mangler',
        noImage: 'Bilde mangler',
        preview: 'Forhåndsvisning',
        previewDescription: 'Eksakte resultatoppføringer kan variere basert på innhold og søke relevans.',
        tooLong: 'For lang',
        tooShort: 'For kort'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/nl.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "nl",
    ()=>nl
]);
const nl = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Bijna klaar',
        autoGenerate: 'Automatisch genereren',
        bestPractices: 'best practices',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} tekens, ',
        charactersLeftOver: '{{characters}} tekens over',
        charactersToGo: '{{characters}} tekens te gaan',
        charactersTooMany: '{{characters}} tekens te veel',
        checksPassing: '{{current}}/{{max}} controles geslaagd',
        good: 'Goed',
        imageAutoGenerationTip: 'Automatische generatie haalt de geselecteerde hero-afbeelding op.',
        lengthTipDescription: 'Dit moet tussen {{minLength}} en {{maxLength}} tekens lang zijn. Voor hulp bij het schrijven van kwalitatieve metabeschrijvingen, zie ',
        lengthTipTitle: 'Dit moet tussen {{minLength}} en {{maxLength}} tekens lang zijn. Voor hulp bij het schrijven van kwalitatieve metatitels, zie ',
        missing: 'Ontbreekt',
        noImage: 'Geen afbeelding',
        preview: 'Voorbeeld',
        previewDescription: 'Exacte zoekresultaten kunnen variëren op basis van inhoud en zoekrelevantie.',
        tooLong: 'Te lang',
        tooShort: 'Te kort'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/pl.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "pl",
    ()=>pl
]);
const pl = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Prawie gotowe',
        autoGenerate: 'Wygeneruj automatycznie',
        bestPractices: 'najlepsze praktyki',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} znaków, ',
        charactersLeftOver: 'zostało {{characters}} znaków',
        charactersToGo: 'pozostało {{characters}} znaków',
        charactersTooMany: '{{characters}} znaków za dużo',
        checksPassing: '{{current}}/{{max}} testów zakończonych pomyślnie',
        good: 'Dobrze',
        imageAutoGenerationTip: 'Automatyczne generowanie pobierze wybrany główny obraz.',
        lengthTipDescription: 'Długość powinna wynosić od {{minLength}} do {{maxLength}} znaków. Po porady dotyczące pisania wysokiej jakości meta opisów zobacz ',
        lengthTipTitle: 'Długość powinna wynosić od {{minLength}} do {{maxLength}} znaków. Po porady dotyczące pisania wysokiej jakości meta tytułów zobacz ',
        missing: 'Brakuje',
        noImage: 'Brak obrazu',
        preview: 'Podgląd',
        previewDescription: 'Dokładne wyniki listowania mogą się różnić w zależności od treści i zgodności z kryteriami wyszukiwania.',
        tooLong: 'Zbyt długie',
        tooShort: 'Zbyt krótkie'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/pt.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "pt",
    ()=>pt
]);
const pt = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Quase lá',
        autoGenerate: 'Gerar automaticamente',
        bestPractices: 'melhores práticas',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caracteres, ',
        charactersLeftOver: '{{characters}} caracteres a mais',
        charactersToGo: '{{characters}} caracteres restantes',
        charactersTooMany: '{{characters}} caracteres em excesso',
        checksPassing: '{{current}}/{{max}} verificações aprovadas',
        good: 'Bom',
        imageAutoGenerationTip: 'A geração automática buscará a imagem destacada selecionada.',
        lengthTipDescription: 'Isso deve ter entre {{minLength}} e {{maxLength}} caracteres. Para obter ajuda na escrita de descrições meta de qualidade, veja ',
        lengthTipTitle: 'Isso deve ter entre {{minLength}} e {{maxLength}} caracteres. Para obter ajuda na escrita de títulos meta de qualidade, veja ',
        missing: 'Ausente',
        noImage: 'Nenhuma imagem',
        preview: 'Pré-visualização',
        previewDescription: 'Os resultados exatos podem variar com base no conteúdo e na relevância da pesquisa.',
        tooLong: 'Muito longo',
        tooShort: 'Muito curto'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ro.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ro",
    ()=>ro
]);
const ro = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Aproape gata',
        autoGenerate: 'Generare automată',
        bestPractices: 'bune practici',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} caractere, ',
        charactersLeftOver: '{{characters}} caractere în plus',
        charactersToGo: '{{characters}} caractere rămase',
        charactersTooMany: '{{characters}} caractere prea multe',
        checksPassing: '{{current}}/{{max}} verificări trecute',
        good: 'Bun',
        imageAutoGenerationTip: 'Generarea automată va prelua imaginea reprezentativă selectată.',
        lengthTipDescription: 'Aceasta ar trebui să aibă între {{minLength}} și {{maxLength}} caractere. Pentru ajutor în redactarea descrierilor meta de calitate, vezi ',
        lengthTipTitle: 'Aceasta ar trebui să aibă între {{minLength}} și {{maxLength}} caractere. Pentru ajutor în redactarea titlurilor meta de calitate, vezi ',
        missing: 'Lipsește',
        noImage: 'Nicio imagine',
        preview: 'Previzualizare',
        previewDescription: 'Rezultatele exacte pot varia în funcție de conținut și relevanța căutării.',
        tooLong: 'Prea lung',
        tooShort: 'Prea scurt'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/rs.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "rs",
    ()=>rs
]);
const rs = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Скоро готово',
        autoGenerate: 'Аутоматски генериши',
        bestPractices: 'најбоље праксе',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} карактера, ',
        charactersLeftOver: '{{characters}} карактера вишка',
        charactersToGo: '{{characters}} карактера преостало',
        charactersTooMany: '{{characters}} карактера превише',
        checksPassing: '{{current}}/{{max}} провера успешно прошло',
        good: 'Добро',
        imageAutoGenerationTip: 'Аутоматско генерисање ће преузети изабрану херо слику.',
        lengthTipDescription: 'Ово треба да има између {{minLength}} и {{maxLength}} карактера. За помоћ у писању квалитетних мета описа, погледајте ',
        lengthTipTitle: 'Ово треба да има између {{minLength}} и {{maxLength}} карактера. За помоћ у писању квалитетних мета наслова, погледајте ',
        missing: 'Недостаје',
        noImage: 'Нема слике',
        preview: 'Преглед',
        previewDescription: 'Тачни резултати претраге могу варирати у зависности од садржаја и релевантности претраге.',
        tooLong: 'Предугачко',
        tooShort: 'Прекратко'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/rsLatin.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "rsLatin",
    ()=>rsLatin
]);
const rsLatin = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Skoro gotovo',
        autoGenerate: 'Automatski generiši',
        bestPractices: 'najbolje prakse',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} karaktera, ',
        charactersLeftOver: '{{characters}} karaktera viška',
        charactersToGo: '{{characters}} karaktera preostalo',
        charactersTooMany: '{{characters}} karaktera previše',
        checksPassing: '{{current}}/{{max}} provera uspešno prošlo',
        good: 'Dobro',
        imageAutoGenerationTip: 'Automatsko generisanje će preuzeti izabranu hero sliku.',
        lengthTipDescription: 'Ovo treba da ima između {{minLength}} i {{maxLength}} karaktera. Za pomoć u pisanju kvalitetnih meta opisa, pogledajte ',
        lengthTipTitle: 'Ovo treba da ima između {{minLength}} i {{maxLength}} karaktera. Za pomoć u pisanju kvalitetnih meta naslova, pogledajte ',
        missing: 'Nedostaje',
        noImage: 'Nema slike',
        preview: 'Pregled',
        previewDescription: 'Tačni rezultati pretrage mogu varirati u zavisnosti od sadržaja i relevantnosti pretrage.',
        tooLong: 'Predugačko',
        tooShort: 'Prekratko'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ru.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ru",
    ()=>ru
]);
const ru = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Почти готово',
        autoGenerate: 'Сгенерировать автоматически',
        bestPractices: 'лучшие практики',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} символов, ',
        charactersLeftOver: 'осталось {{characters}} символов',
        charactersToGo: 'на {{characters}} символов меньше',
        charactersTooMany: 'на {{characters}} символов больше',
        checksPassing: '{{current}}/{{max}} проверок пройдено',
        good: 'Хорошо',
        imageAutoGenerationTip: 'Автогенерация использует выбранное главное изображение.',
        lengthTipDescription: 'Должно быть от {{minLength}} до {{maxLength}} символов. Для помощи в написании качественных метаописаний см.',
        lengthTipTitle: 'Должно быть от {{minLength}} до {{maxLength}} символов. Для помощи в написании качественных метазаголовков см.',
        missing: 'Отсутствует',
        noImage: 'Нет изображения',
        preview: 'Предварительный просмотр',
        previewDescription: 'Фактические результаты могут отличаться в зависимости от контента и релевантности поиска.',
        tooLong: 'Слишком длинно',
        tooShort: 'Слишком коротко'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sk.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "sk",
    ()=>sk
]);
const sk = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Takmer hotovo',
        autoGenerate: 'Automaticky generovať',
        bestPractices: 'najlepšie postupy',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} znakov, ',
        charactersLeftOver: '{{characters}} znakov navyše',
        charactersToGo: 'Ešte {{characters}} znakov',
        charactersTooMany: '{{characters}} znakov navyše',
        checksPassing: '{{current}}/{{max}} kontrol prešlo',
        good: 'Dobre',
        imageAutoGenerationTip: 'Automatické generovanie načíta vybraný hlavný obrázok.',
        lengthTipDescription: 'Tento text by mal mať medzi {{minLength}} a {{maxLength}} znakmi. Ak potrebujete pomoc s písaním kvalitných meta popisov, pozrite si ',
        lengthTipTitle: 'Tento text by mal mať medzi {{minLength}} a {{maxLength}} znakmi. Ak potrebujete pomoc s písaním kvalitných meta nadpisov, pozrite si ',
        missing: 'Chýba',
        noImage: 'Žiadny obrázok',
        preview: 'Náhľad',
        previewDescription: 'Presné výsledky vyhľadávania sa môžu líšiť v závislosti od obsahu a relevantnosti vyhľadávania.',
        tooLong: 'Príliš dlhé',
        tooShort: 'Príliš krátke'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sl.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "sl",
    ()=>sl
]);
const sl = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Skoraj končano',
        autoGenerate: 'Samodejno generiranje',
        bestPractices: 'najboljše prakse',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} znakov, ',
        charactersLeftOver: '{{characters}} znakov preveč',
        charactersToGo: '{{characters}} znakov preostalo',
        charactersTooMany: '{{characters}} znakov preveč',
        checksPassing: '{{current}}/{{max}} preverjanj je uspelo',
        good: 'Dobro',
        imageAutoGenerationTip: 'Samodejno generiranje bo preneslo izbrano glavno sliko.',
        lengthTipDescription: 'To naj bo dolgo med {{minLength}} in {{maxLength}} znakov. Za pomoč pri pisanju kakovostnih meta opisov si oglejte ',
        lengthTipTitle: 'To naj bo dolgo med {{minLength}} in {{maxLength}} znakov. Za pomoč pri pisanju kakovostnih meta naslovov si oglejte ',
        missing: 'Manjkajoče',
        noImage: 'Brez slike',
        preview: 'Predogled',
        previewDescription: 'Natančni rezultati iskanja se lahko razlikujejo glede na vsebino in relevantnost iskanja.',
        tooLong: 'Presega dovoljeno dolžino',
        tooShort: 'Prekratka dolžina'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/sv.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "sv",
    ()=>sv
]);
const sv = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Nästan klar',
        autoGenerate: 'Skapa automatiskt',
        bestPractices: 'bästa praxis',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} tecken, ',
        charactersLeftOver: '{{characters}} tecken blir över',
        charactersToGo: '{{characters}} tecken kvar',
        charactersTooMany: '{{characters}} tecken för mycket',
        checksPassing: '{{current}}/{{max}} kontroller är godkända',
        good: 'Bra',
        imageAutoGenerationTip: 'Den automatiska processen kommer att välja en hero-bild.',
        lengthTipDescription: 'Bör vara mellan {{minLength}} och {{maxLength}} tecken. För hjälp med att skriva bra metabeskrivningar, se ',
        lengthTipTitle: 'Bör vara mellan {{minLength}} och {{maxLength}} tecken. För hjälp med att skriva bra metatitlar, se ',
        missing: 'Saknas',
        noImage: 'Ingen bild',
        preview: 'Förhandsgranska',
        previewDescription: 'Exakta resultatlistningar kan variera baserat på innehåll och sökrelevans.',
        tooLong: 'För lång',
        tooShort: 'För kort'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/ta.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ta",
    ()=>ta
]);
const ta = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'கிட்டத்தட்ட முடிந்துவிட்டது',
        autoGenerate: 'தானாக உருவாக்கு',
        bestPractices: 'சிறந்த நடைமுறைகள்',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} எழுத்துகள், ',
        charactersLeftOver: '{{characters}} மீதம் உள்ளது',
        charactersToGo: '{{characters}} எழுத வேண்டும்',
        charactersTooMany: '{{characters}} அதிகமாக உள்ளது',
        checksPassing: '{{current}}/{{max}} சோதனைகள் வெற்றி',
        good: 'நன்று',
        imageAutoGenerationTip: 'தானியங்கு உருவாக்கம் தேர்ந்தெடுக்கப்பட்ட முக்கியப் படத்தை எடுக்கும்.',
        lengthTipDescription: 'இது {{minLength}} மற்றும் {{maxLength}} எழுத்துகளுக்கு இடையில் இருக்க வேண்டும். தரமான மெட்டா விளக்கங்களை எழுத உதவிக்கு பார்க்கவும் ',
        lengthTipTitle: 'இது {{minLength}} மற்றும் {{maxLength}} எழுத்துகளுக்கு இடையில் இருக்க வேண்டும். தரமான மெட்டா தலைப்புகளை எழுத உதவிக்கு பார்க்கவும் ',
        missing: 'இல்லை',
        noImage: 'படம் இல்லை',
        preview: 'முன்னோட்டம்',
        previewDescription: 'சரியான முடிவு பட்டியல்கள் உள்ளடக்கம் மற்றும் தேடல் தொடர்புக்கு ஏற்ப மாறலாம்.',
        tooLong: 'மிக நீளம்',
        tooShort: 'மிகக் குறைவு'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/th.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "th",
    ()=>th
]);
const th = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'เกือบเสร็จแล้ว',
        autoGenerate: 'สร้างอัตโนมัติ',
        bestPractices: 'แนวปฏิบัติที่ดีที่สุด',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} ตัวอักษร, ',
        charactersLeftOver: '{{characters}} ตัวอักษรที่เหลือ',
        charactersToGo: '{{characters}} ตัวอักษรที่ต้องการ',
        charactersTooMany: '{{characters}} ตัวอักษรเกินไป',
        checksPassing: '{{current}}/{{max}} การตรวจสอบสำเร็จ',
        good: 'ดี',
        imageAutoGenerationTip: 'การสร้างอัตโนมัติจะดึงภาพหลักที่เลือก',
        lengthTipDescription: 'ข้อความนี้ควรมีระหว่าง {{minLength}} และ {{maxLength}} ตัวอักษร สำหรับคำแนะนำในการเขียนคำอธิบายเมตาคุณภาพสูง โปรดดูที่ ',
        lengthTipTitle: 'ข้อความนี้ควรมีระหว่าง {{minLength}} และ {{maxLength}} ตัวอักษร สำหรับคำแนะนำในการเขียนหัวข้อเมตาคุณภาพสูง โปรดดูที่ ',
        missing: 'ขาดหายไป',
        noImage: 'ไม่มีภาพ',
        preview: 'ตัวอย่าง',
        previewDescription: 'ผลลัพธ์การค้นหาที่แท้จริงอาจแตกต่างกันไปตามเนื้อหาและความเกี่ยวข้องของการค้นหา',
        tooLong: 'ยาวเกินไป',
        tooShort: 'สั้นเกินไป'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/tr.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "tr",
    ()=>tr
]);
const tr = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Neredeyse tamam',
        autoGenerate: 'Otomatik oluştur',
        bestPractices: 'en iyi uygulamalar',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} karakter, ',
        charactersLeftOver: '{{characters}} karakter kaldı',
        charactersToGo: '{{characters}} karakter kaldı',
        charactersTooMany: '{{characters}} karakter fazla',
        checksPassing: '{{current}}/{{max}} kontrol başarılı',
        good: 'İyi',
        imageAutoGenerationTip: 'Otomatik oluşturma, seçilen ana görseli alacaktır.',
        lengthTipDescription: '{{minLength}} ile {{maxLength}} karakter arasında olmalıdır. Kaliteli meta açıklamaları yazmak için yardım almak için bkz. ',
        lengthTipTitle: '{{minLength}} ile {{maxLength}} karakter arasında olmalıdır. Kaliteli meta başlıkları yazmak için yardım almak için bkz. ',
        missing: 'Eksik',
        noImage: 'Görsel yok',
        preview: 'Önizleme',
        previewDescription: 'Kesin sonuç listeleri içeriğe ve arama alâkasına göre değişebilir.',
        tooLong: 'Çok uzun',
        tooShort: 'Çok kısa'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/uk.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "uk",
    ()=>uk
]);
const uk = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Ще трошки',
        autoGenerate: 'Згенерувати',
        bestPractices: 'найкращі практики',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} символів, ',
        charactersLeftOver: 'залишилось {{characters}} символів',
        charactersToGo: ' на {{characters}} символів коротше',
        charactersTooMany: 'на {{characters}} символів довше',
        checksPassing: '{{current}}/{{max}} перевірок пройдено',
        good: 'Чудово',
        imageAutoGenerationTip: 'Автоматична генерація використає зображення з головного блоку',
        lengthTipDescription: 'Має бути від {{minLength}} до {{maxLength}} символів. Щоб дізнатися, як писати якісні метаописи — перегляньте ',
        lengthTipTitle: 'Має бути від {{minLength}} до {{maxLength}} символів. Щоб дізнатися, як писати якісні метазаголовки — перегляньте ',
        missing: 'Відсутнє',
        noImage: 'Немає зображення',
        preview: 'Попередній перегляд',
        previewDescription: 'Реальне відображення може відрізнятися в залежності від вмісту та релевантності пошуку.',
        tooLong: 'Задовгий',
        tooShort: 'Закороткий'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/vi.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "vi",
    ()=>vi
]);
const vi = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: 'Gần đạt',
        autoGenerate: 'Tự động tạo',
        bestPractices: 'các phương pháp hay nhất',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} kí tự, ',
        charactersLeftOver: 'còn lại {{characters}}',
        charactersToGo: 'Còn {{characters}} ký tự nữa',
        charactersTooMany: 'vượt quá {{characters}} ký tự',
        checksPassing: '{{current}}/{{max}} đã đạt',
        good: 'Tốt',
        imageAutoGenerationTip: 'Tính năng tự động tạo sẽ lấy ảnh đầu tiên được chọn.',
        lengthTipDescription: 'Độ dài nên từ {{minLength}}-{{maxLength}} kí tự. Để được hướng dẫn viết mô tả meta chất lượng, hãy xem ',
        lengthTipTitle: 'Độ dài nên từ {{minLength}}-{{maxLength}} kí tự. Để được hướng dẫn viết mô tả meta chất lượng, hãy xem ',
        missing: 'Không đạt',
        noImage: 'Chưa có ảnh',
        preview: 'Xem trước',
        previewDescription: 'Kết quả hiển thị có thể thay đổi tuỳ theo nội dung và công cụ tìm kiếm.',
        tooLong: 'Quá dài',
        tooShort: 'Quá ngắn'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/zh.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "zh",
    ()=>zh
]);
const zh = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: '快完成了',
        autoGenerate: '自动生成',
        bestPractices: '最佳实践',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} 字符, ',
        charactersLeftOver: '{{characters}} 字符剩余',
        charactersToGo: '{{characters}} 字符待输入',
        charactersTooMany: '{{characters}} 字符太多',
        checksPassing: '{{current}}/{{max}} 检查通过',
        good: '好',
        imageAutoGenerationTip: '自动生成将获取选定的主图像。',
        lengthTipDescription: '此文本应介于 {{minLength}} 和 {{maxLength}} 个字符之间。如需有关编写高质量 meta 描述的帮助，请参见 ',
        lengthTipTitle: '此文本应介于 {{minLength}} 和 {{maxLength}} 个字符之间。如需有关编写高质量 meta 标题的帮助，请参见 ',
        missing: '缺失',
        noImage: '没有图片',
        preview: '预览',
        previewDescription: '实际搜索结果可能会根据内容和搜索相关性有所不同。',
        tooLong: '太长',
        tooShort: '太短'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/plugin-seo/dist/translations/zhTw.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "zhTw",
    ()=>zhTw
]);
const zhTw = {
    $schema: './translation-schema.json',
    'plugin-seo': {
        almostThere: '快完成了',
        autoGenerate: '自動產生',
        bestPractices: '最佳做法',
        characterCount: '{{current}}/{{minLength}}-{{maxLength}} 字元，',
        charactersLeftOver: '多出 {{characters}} 個字元',
        charactersToGo: '還差 {{characters}} 個字元',
        charactersTooMany: '超出 {{characters}} 個字元',
        checksPassing: '{{current}} 項檢查通過，共 {{max}} 項',
        good: '良好',
        imageAutoGenerationTip: '系統會自動擷取選取的主圖。',
        lengthTipDescription: '長度應介於 {{minLength}} 到 {{maxLength}} 個字元。若需撰寫高品質後設資料描述的協助，請參閱',
        lengthTipTitle: '長度應介於 {{minLength}} 到 {{maxLength}} 個字元。若需撰寫高品質後設資料標題的協助，請參閱',
        missing: '尚未設定',
        noImage: '沒有圖片',
        preview: '預覽',
        previewDescription: '實際搜尋結果可能會因內容與關聯性而有所不同。',
        tooLong: '過長',
        tooShort: '過短'
    }
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/translations/dist/languages/ru.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ru",
    ()=>ru,
    "ruTranslations",
    ()=>ruTranslations
]);
const ruTranslations = {
    authentication: {
        account: 'Аккаунт',
        accountOfCurrentUser: 'Аккаунт текущего пользователя',
        accountVerified: 'Учетная запись успешно подтверждена.',
        alreadyActivated: 'Уже активирован',
        alreadyLoggedIn: 'Уже вошли в систему',
        apiKey: 'API ключ',
        authenticated: 'Аутентифицирован',
        backToLogin: 'Вернуться к входу',
        beginCreateFirstUser: 'Чтобы начать - создайте первого пользователя.',
        changePassword: 'Сменить пароль',
        checkYourEmailForPasswordReset: 'Если указанный адрес электронной почты связан с аккаунтом, вы скоро получите инструкции по сбросу пароля. Пожалуйста, проверьте папку со спамом или нежелательной почтой, если вы не видите письма во входящих.',
        confirmGeneration: 'Подтвердить генерацию',
        confirmPassword: 'Подтверждение пароля',
        createFirstUser: 'Создание первого пользователя',
        emailNotValid: 'Указанный адрес электронной почты неверен',
        emailOrUsername: 'Электронная почта или Имя пользователя',
        emailSent: 'Email отправлен',
        emailVerified: 'Электронная почта успешно подтверждена.',
        enableAPIKey: 'Активировать API ключ',
        failedToUnlock: 'Не удалось разблокировать',
        forceUnlock: 'Принудительная разблокировка',
        forgotPassword: 'Забыли пароль',
        forgotPasswordEmailInstructions: 'Пожалуйста, введите ваш email. Вы получите письмо с инструкцией по восстановлению пароля.',
        forgotPasswordQuestion: 'Забыли пароль?',
        forgotPasswordUsernameInstructions: 'Пожалуйста, введите ваше имя пользователя ниже. Инструкции по сбросу вашего пароля будут отправлены на адрес электронной почты, связанный с вашим именем пользователя.',
        generate: 'Сгенерировать',
        generateNewAPIKey: 'Сгенерировать новый API ключ',
        generatingNewAPIKeyWillInvalidate: 'Генерация нового API ключа приведёт к <1>недействительности</1> предыдущего ключа. Вы уверены, что хотите продолжить?',
        lockUntil: 'Заблокировать до',
        logBackIn: 'Войти снова',
        loggedIn: 'Чтобы войти в другую учетную запись, сначала <0>выйдите</0>.',
        loggedInChangePassword: 'Чтобы изменить пароль, зайдите в свой <0>аккаунт</0> и измените пароль там.',
        loggedOutInactivity: 'Вы вышли из системы из-за неактивности.',
        loggedOutSuccessfully: 'Вы успешно вышли из системы.',
        loggingOut: 'Выход из системы...',
        login: 'Войти',
        loginAttempts: 'Попытки входа',
        loginUser: 'Вход пользователя в систему',
        loginWithAnotherUser: 'Чтобы войти в систему под другим пользователем, необходимо сначала <0>выйти</0>.',
        logOut: 'Выйти',
        logout: 'Выйти',
        logoutSuccessful: 'Выход выполнен успешно.',
        logoutUser: 'Вход из системы',
        newAccountCreated: 'Новый аккаунт был создан для доступа к <a href="{{serverURL}}">{{serverURL}}</a> Пожалуйста, кликните по следующей ссылке или вставьте в адресную строку браузера чтобы подтвердить email: <a href="{{verificationURL}}">{{verificationURL}}</a><br> После подтверждения вашего email, вы сможете успешно войти в систему.',
        newAPIKeyGenerated: 'Новый API ключ сгенерирован.',
        newPassword: 'Новый пароль',
        passed: 'Аутентификация пройдена',
        passwordResetSuccessfully: 'Сброс пароля успешно выполнен.',
        resetPassword: 'Сброс пароля',
        resetPasswordExpiration: 'Сброс пароля по истечении срока действия',
        resetPasswordToken: 'Токен сброса пароля',
        resetYourPassword: 'Сброс вашего пароля',
        stayLoggedIn: 'Остаться в системе',
        successfullyRegisteredFirstUser: 'Успешно зарегистрирован первый пользователь.',
        successfullyUnlocked: 'Успешно разблокирован',
        tokenRefreshSuccessful: 'Обновление токена прошло успешно.',
        unableToVerify: 'Невозможно подтвердить',
        username: 'Имя пользователя',
        usernameNotValid: 'Предоставленное имя пользователя недействительно.',
        verified: 'Подтверждено',
        verifiedSuccessfully: 'Успешно подтверждено',
        verify: 'Подтвердить',
        verifyUser: 'Подтвердить пользователя',
        verifyYourEmail: 'Подтвердить ваш email',
        youAreInactive: 'Вы не были активны в течение некоторого времени и скоро автоматически выйдете из системы в целях вашей безопасности. Вы хотите остаться в системе?',
        youAreReceivingResetPassword: 'Вы получили это сообщение, потому что вы (или кто-то другой) запросили сброс пароля для вашей учетной записи. Пожалуйста, нажмите на следующую ссылку или вставьте ее в браузер, чтобы завершить процесс:',
        youDidNotRequestPassword: 'Если вы не запрашивали этого, пожалуйста, проигнорируйте это письмо, и ваш пароль останется неизменным.'
    },
    dashboard: {
        addButton: 'Добавить +',
        addWidget: 'Добавить виджет',
        deleteWidget: 'Удалить виджет {{id}}',
        discardConfirmLabel: 'Отклонить',
        discardMessage: 'У вас есть несохраненные изменения в макете вашей панели управления. Вы уверены, что хотите их отменить?',
        discardTitle: 'Отменить изменения?',
        editDashboard: 'Редактировать панель управления',
        editingDashboard: 'Панель редактирования',
        noItems: 'На вашей панели нет виджетов. Вы можете добавить их из меню "Панель управления", расположенного в верхней панели.',
        resetLayout: 'Сбросить Макет',
        searchWidgets: 'Поиск виджетов...'
    },
    error: {
        accountAlreadyActivated: 'Этот аккаунт уже был активирован.',
        autosaving: 'При автосохранении этого документа возникла проблема.',
        correctInvalidFields: 'Пожалуйста, исправьте неправильные поля.',
        deletingFile: 'Произошла ошибка при удалении файла.',
        deletingTitle: 'При удалении {{title}} произошла ошибка. Пожалуйста, проверьте соединение и повторите попытку.',
        documentNotFound: 'Документ с ID {{id}} не удалось найти. Возможно, он был удален или никогда не существовал, или у вас нет доступа к нему.',
        emailOrPasswordIncorrect: 'Указанный email или пароль неверен.',
        failedToResetLayout: 'Не удалось сбросить макет.',
        failedToSaveLayout: 'Не удалось сохранить макет.',
        followingFieldsInvalid_one: 'Следующее поле недействительно:',
        followingFieldsInvalid_other: 'Следующие поля недействительны:',
        incorrectCollection: 'Неправильная Коллекция',
        insufficientClipboardPermissions: 'Доступ к буферу обмена отклонен. Проверьте разрешения буфера обмена.',
        invalidClipboardData: 'Неверные данные в буфере обмена.',
        invalidFileType: 'Недопустимый тип файла',
        invalidFileTypeValue: 'Недопустимый тип файла: {{value}}',
        invalidRequestArgs: 'В запрос переданы недопустимые аргументы: {{args}}',
        loadingDocument: 'Возникла проблема при загрузке документа с ID {{id}}.',
        localesNotSaved_one: 'Следующую локализацию не удалось сохранить:',
        localesNotSaved_other: 'Следующие локализации не удалось сохранить:',
        logoutFailed: 'Выход не удался.',
        missingEmail: 'Отсутствует email.',
        missingIDOfDocument: 'Отсутствующий ID документа для обновления.',
        missingIDOfVersion: 'Отсутствует ID версии.',
        missingRequiredData: 'Отсутствуют необходимые данные.',
        noFilesUploaded: 'Не было загружено ни одного файла.',
        noMatchedField: 'Не найдено подходящего поля для "{{label}}"',
        notAllowedToAccessPage: 'Вы не имеете права доступа к этой странице.',
        notAllowedToPerformAction: 'У вас нет права на выполнение этого действия.',
        notFound: 'Запрашиваемый ресурс не найден.',
        noUser: 'Нет Пользователя',
        previewing: 'При предварительном просмотре этого документа возникла проблема.',
        problemUploadingFile: 'Возникла проблема при загрузке файла.',
        restoringTitle: 'Произошла ошибка при восстановлении {{title}}. Пожалуйста, проверьте свое соединение и попробуйте снова.',
        revertingDocument: 'Возникла проблема при возврате этого документа.',
        tokenInvalidOrExpired: 'Токен либо недействителен, либо срок его действия истек.',
        tokenNotProvided: 'Токен не предоставлен.',
        unableToCopy: 'Не удалось скопировать.',
        unableToDeleteCount: 'Не удалось удалить {{count}} из {{total}} {{label}}.',
        unableToReindexCollection: 'Ошибка при переиндексации коллекции {{collection}}. Операция прервана.',
        unableToUpdateCount: 'Не удалось обновить {{count}} из {{total}} {{label}}.',
        unauthorized: 'Нет доступа, вы должны войти, чтобы сделать этот запрос.',
        unauthorizedAdmin: 'Нет доступа, этот пользователь не имеет доступа к панели администратора.',
        unknown: 'Произошла неизвестная ошибка.',
        unPublishingDocument: 'При отмене публикации этого документа возникла проблема.',
        unspecific: 'Произошла ошибка.',
        unverifiedEmail: 'Пожалуйста, подтвердите свою электронную почту перед входом.',
        userEmailAlreadyRegistered: 'Пользователь с указанным email уже зарегистрирован.',
        userLocked: 'Этот пользователь заблокирован из-за слишком большого количества неудачных попыток входа.',
        usernameAlreadyRegistered: 'Пользователь с данным именем пользователя уже зарегистрирован.',
        usernameOrPasswordIncorrect: 'Указанное имя пользователя или пароль неверны.',
        valueMustBeUnique: 'Значение должно быть уникальным',
        verificationTokenInvalid: 'Проверочный токен недействителен.'
    },
    fields: {
        addLabel: 'Добавить {{label}}',
        addLink: 'Добавить ссылку',
        addNew: 'Добавить новый',
        addNewLabel: 'Добавить {{label}}',
        addRelationship: 'Добавить Отношения',
        addUpload: 'Добавить загрузку',
        block: 'Блок',
        blocks: 'Блоки',
        blockType: 'Тип Блока',
        chooseBetweenCustomTextOrDocument: 'Выберите между вводом пользовательского текстового URL и ссылкой на другой документ.',
        chooseDocumentToLink: 'Выберите документ для ссылки',
        chooseFromExisting: 'Выбрать из существующих',
        chooseLabel: 'Выбрать {{label}}',
        collapseAll: 'Свернуть все',
        customURL: 'Пользовательский URL',
        editLabelData: 'Редактировать данные {{label}}',
        editLink: 'Редактировать ссылку',
        editRelationship: 'Редактировать Отношения',
        enterURL: 'Введите URL',
        internalLink: 'Внутренняя ссылка',
        itemsAndMore: '{{items}} и ещё {{count}}',
        labelRelationship: '{{label}} Отношения',
        latitude: 'Широта',
        linkedTo: 'Связано с <0>{{label}}</0>',
        linkType: 'Тип ссылки',
        longitude: 'Долгота',
        newLabel: 'Новый {{label}}',
        openInNewTab: 'Открывать в новой вкладке',
        passwordsDoNotMatch: 'Пароли не совпадают.',
        relatedDocument: 'Связанный документ',
        relationTo: 'Отношение к',
        removeRelationship: 'Удалить связь',
        removeUpload: 'Удалить загруженное',
        saveChanges: 'Сохранить изменения',
        searchForBlock: 'Найти Блок',
        searchForLanguage: 'Поиск языка',
        selectExistingLabel: 'Выберите существующий {{label}}',
        selectFieldsToEdit: 'Выберите поля для редактирования',
        showAll: 'Показать все',
        swapRelationship: 'Поменять отношения',
        swapUpload: 'Заменить загруженное',
        textToDisplay: 'Текст для отображения',
        toggleBlock: 'Переключить Блок',
        uploadNewLabel: 'Загрузить новый {{label}}'
    },
    folder: {
        browseByFolder: 'Просмотр по папкам',
        byFolder: 'По папке',
        deleteFolder: 'Удалить папку',
        folderName: 'Название папки',
        folders: 'Папки',
        folderTypeDescription: 'Выберите, какие типы документов коллекции должны быть разрешены в этой папке.',
        itemHasBeenMoved: '{{title}} был перемещен в {{folderName}}',
        itemHasBeenMovedToRoot: '{{title}} был перемещен в корневую папку',
        itemsMovedToFolder: '{{title}} перемещен в {{folderName}}',
        itemsMovedToRoot: '{{title}} перемещен в корневую папку',
        moveFolder: 'Переместить папку',
        moveItemsToFolderConfirmation: 'Вы собираетесь переместить <1>{{count}} {{label}}</1> в <2>{{toFolder}}</2>. Вы уверены?',
        moveItemsToRootConfirmation: 'Вы собираетесь перенести <1>{{count}} {{label}}</1> в корневую папку. Вы уверены?',
        moveItemToFolderConfirmation: 'Вы собираетесь переместить <1>{{title}}</1> в <2>{{toFolder}}</2>. Вы уверены?',
        moveItemToRootConfirmation: 'Вы собираетесь переместить <1>{{title}}</1> в корневую папку. Вы уверены?',
        movingFromFolder: 'Перемещение {{title}} из {{fromFolder}}',
        newFolder: 'Новая папка',
        noFolder: 'Нет папки',
        renameFolder: 'Переименовать папку',
        searchByNameInFolder: 'Поиск по имени в {{folderName}}',
        selectFolderForItem: 'Выберите папку для {{title}}'
    },
    general: {
        name: 'Имя',
        aboutToDelete: 'Вы собираетесь удалить {{label}} <1>{{title}}</1>. Вы уверены?',
        aboutToDeleteCount_many: 'Вы собираетесь удалить {{count}} {{label}}',
        aboutToDeleteCount_one: 'Вы собираетесь удалить {{count}} {{label}}',
        aboutToDeleteCount_other: 'Вы собираетесь удалить {{count}} {{label}}',
        aboutToPermanentlyDelete: 'Вы собираетесь навсегда удалить {{label}} <1>{{title}}</1>. Вы уверены?',
        aboutToPermanentlyDeleteTrash: 'Вы собираетесь навсегда удалить <0>{{count}}</0> <1>{{label}}</1> из корзины. Вы уверены?',
        aboutToRestore: 'Вы собираетесь восстановить {{label}} <1>{{title}}</1>. Вы уверены?',
        aboutToRestoreAsDraft: 'Вы собираетесь восстановить {{label}} <1>{{title}}</1> как черновик. Вы уверены?',
        aboutToRestoreAsDraftCount: 'Вы собираетесь восстановить {{count}} {{label}} как черновик',
        aboutToRestoreCount: 'Вы собираетесь восстановить {{count}} {{label}}',
        aboutToTrash: 'Вы собираетесь переместить {{label}} <1>{{title}}</1> в корзину. Вы уверены?',
        aboutToTrashCount: 'Вы собираетесь переместить {{count}} {{label}} в корзину',
        addBelow: 'Добавить ниже',
        addFilter: 'Добавить фильтр',
        adminTheme: 'Тема Панели',
        all: 'Все',
        allCollections: 'Все Коллекции',
        allLocales: 'Все локали',
        and: 'А также',
        anotherUser: 'Другой пользователь',
        anotherUserTakenOver: 'Другой пользователь взял на себя редактирование этого документа.',
        applyChanges: 'Применить изменения',
        ascending: 'Восходящий',
        automatic: 'Автоматически',
        backToDashboard: 'Назад к Панели',
        cancel: 'Отмена',
        changesNotSaved: 'Ваши изменения не были сохранены. Если вы сейчас уйдете, то потеряете свои изменения.',
        clear: 'Четкий',
        clearAll: 'Очистить все',
        close: 'Закрыть',
        collapse: 'Свернуть',
        collections: 'Коллекции',
        columns: 'Колонки',
        columnToSort: 'Колонка для сортировки',
        confirm: 'Подтвердить',
        confirmCopy: 'Подтвердить копирование',
        confirmDeletion: 'Подтвердить удаление',
        confirmDuplication: 'Подтвердить копирование',
        confirmMove: 'Подтвердите перемещение',
        confirmReindex: 'Переиндексировать все {{collections}}?',
        confirmReindexAll: 'Переиндексировать все коллекции?',
        confirmReindexDescription: 'Это удалит существующие индексы и переиндексирует документы в коллекциях {{collections}}.',
        confirmReindexDescriptionAll: 'Это удалит существующие индексы и переиндексирует документы во всех коллекциях.',
        confirmRestoration: 'Подтвердите восстановление',
        copied: 'Скопировано',
        copy: 'Скопировать',
        copyField: 'Копировать поле',
        copying: 'Копирование',
        copyRow: 'Копировать строку',
        copyWarning: 'Вы собираетесь перезаписать {{to}} на {{from}} для {{label}} {{title}}. Вы уверены?',
        create: 'Создать',
        created: 'Создано',
        createdAt: 'Дата создания',
        createNew: 'Создать',
        createNewLabel: 'Создать новый {{label}}',
        creating: 'Создание',
        creatingNewLabel: 'Создание нового {{label}}',
        currentlyEditing: 'в настоящее время редактирует этот документ. Если вы возьмете на себя, они будут заблокированы от продолжения редактирования и могут потерять несохраненные изменения.',
        custom: 'Обычай',
        dark: 'Тёмная',
        dashboard: 'Панель',
        delete: 'Удалить',
        deleted: 'Удалено',
        deletedAt: 'Удалено В',
        deletedCountSuccessfully: 'Удалено {{count}} {{label}} успешно.',
        deletedSuccessfully: 'Удален успешно.',
        deleteLabel: 'Удалить {{label}}',
        deletePermanently: 'Пропустить корзину и удалить навсегда',
        deleting: 'Удаление...',
        depth: 'Глубина',
        descending: 'Уменьшение',
        deselectAllRows: 'Снять выделение со всех строк',
        document: 'Документ',
        documentIsTrashed: 'Этот {{label}} находится в корзине и доступен только для чтения.',
        documentLocked: 'Документ заблокирован',
        documentModified: 'Документ изменен',
        documentOutOfDate: 'Этот документ недавно был обновлен другим пользователем. Ваш просмотр устарел.',
        documents: 'Документы',
        duplicate: 'Дублировать',
        duplicateWithoutSaving: 'Дублирование без сохранения изменений',
        edit: 'Редактировать',
        editAll: 'Редактировать все',
        editedSince: 'Отредактировано с',
        editing: 'Редактирование',
        editingLabel_many: 'Редактирование {{count}} {{label}}',
        editingLabel_one: 'Редактирование {{count}} {{label}}',
        editingLabel_other: 'Редактирование {{count}} {{label}}',
        editingTakenOver: 'Редактирование взято под контроль',
        editLabel: 'Редактировать {{label}}',
        email: 'Email',
        emailAddress: 'Email',
        emptyTrash: 'Очистить корзину',
        emptyTrashLabel: 'Очистить корзину для {{label}}',
        enterAValue: 'Введите значение',
        error: 'Ошибка',
        errors: 'Ошибки',
        exitLivePreview: 'Выйти из режима прямого просмотра',
        export: 'Экспорт',
        fallbackToDefaultLocale: 'Возврат к локали по умолчанию',
        false: 'Ложь',
        filter: 'Фильтр',
        filters: 'Фильтры',
        filterWhere: 'Где фильтровать',
        globals: 'Глобальные',
        goBack: 'Назад',
        groupByLabel: 'Группировать по {{label}}',
        import: 'Импорт',
        isEditing: 'редактирует',
        item: 'Предмет',
        items: 'предметы',
        language: 'Язык',
        lastModified: 'Последнее изменение',
        layout: 'Макет',
        leaveAnyway: 'Все равно уйти',
        leaveWithoutSaving: 'Выход без сохранения',
        light: 'Светлая',
        livePreview: 'Предпросмотр',
        loading: 'Загрузка',
        locale: 'Локаль',
        locales: 'Локали',
        lock: 'Замок',
        menu: 'Меню',
        moreOptions: 'Больше вариантов',
        move: 'Переместить',
        moveConfirm: 'Вы собираетесь переместить {{count}} {{label}} в <1>{{destination}}</1>. Вы уверены?',
        moveCount: 'Переместить {{count}} {{label}}',
        moveDown: 'Сдвинуть вниз',
        moveUp: 'Сдвинуть вверх',
        moving: 'Переезд',
        movingCount: 'Перемещение {{count}} {{label}}',
        newLabel: 'Новый {{label}}',
        newPassword: 'Новый пароль',
        next: 'Следующий',
        no: 'Нет',
        noDateSelected: 'Дата не выбрана',
        noFiltersSet: 'Фильтры не установлены',
        noLabel: 'Без метки',
        none: 'Никто',
        noOptions: 'Нет вариантов',
        noResults: 'Ничего не найдено. Возможно, {{label}} еще не существует или не соответствует указанным фильтрам.',
        noResultsDescription: 'Либо они не существуют, либо не соответствуют указанным вами фильтрам выше.',
        noResultsFound: 'Результатов не найдено.',
        notFound: 'Не найдено',
        nothingFound: 'Ничего не найдено',
        noTrashResults: 'Нет {{label}} в корзине.',
        noUpcomingEventsScheduled: 'Нет запланированных предстоящих событий.',
        noValue: 'Нет значения',
        of: 'из',
        only: 'Только',
        open: 'Открыть',
        openInNewWindow: 'Открыть в новом окне',
        or: 'Или же',
        order: 'Порядок',
        overwriteExistingData: 'Перезаписать существующие данные поля',
        pageNotFound: 'Страница не найдена',
        password: 'Пароль',
        pasteField: 'Вставить поле',
        pasteRow: 'Вставить строку',
        payloadSettings: 'Настройки Payload',
        permanentlyDelete: 'Удалить Навсегда',
        permanentlyDeletedCountSuccessfully: 'Успешно удалено {{count}} {{label}} навсегда.',
        perPage: 'На странице: {{limit}}',
        previous: 'Предыдущий',
        reindex: 'Переиндексировать',
        reindexingAll: 'Переиндексирование всех {{collections}}.',
        reloadDocument: 'Перезагрузить документ',
        remove: 'Удалить',
        rename: 'Переименовать',
        reset: 'Сброс',
        resetPreferences: 'Сбросить настройки',
        resetPreferencesDescription: 'Это сбросит все ваши настройки до значений по умолчанию.',
        resettingPreferences: 'Сброс настроек.',
        restore: 'Восстановить',
        restoreAsPublished: 'Восстановить как опубликованную версию',
        restoredCountSuccessfully: 'Восстановлено успешно {{count}} {{label}}.',
        restoring: 'Восстановление...',
        row: 'Строка',
        rows: 'Строки',
        save: 'Сохранить',
        saveChanges: 'Сохранить изменения',
        saving: 'Сохранение...',
        schedulePublishFor: 'Запланировать публикацию для {{title}}',
        searchBy: 'Искать по',
        select: 'Выбрать',
        selectAll: 'Выбрать все {{count}} {{label}}',
        selectAllRows: 'Выбрать все строки',
        selectedCount: '{{count}} {{label}} выбрано',
        selectLabel: 'Выберите {{label}}',
        selectValue: 'Выбрать значение',
        showAllLabel: 'Показать все {{label}}',
        sorryNotFound: 'К сожалению, ничего подходящего под ваш запрос нет.',
        sort: 'Сортировать',
        sortByLabelDirection: 'Сортировать по {{label}} {{direction}}',
        stayOnThisPage: 'Остаться на этой странице',
        submissionSuccessful: 'Успешно отправлено.',
        submit: 'Отправить',
        submitting: 'Отправка...',
        success: 'Успешно',
        successfullyCreated: '{{label}} успешно создан.',
        successfullyDuplicated: '{{label}} успешно продублирован.',
        successfullyReindexed: 'Успешно переиндексировано {{count}} из {{total}} документов из {{collections}}, пропущено {{skips}} черновиков.',
        takeOver: 'Взять на себя',
        thisLanguage: 'Русский',
        time: 'Время',
        timezone: 'Часовой пояс',
        titleDeleted: '{{label}} {{title}} успешно удалено.',
        titleRestored: '{{label}} "{{title}}" успешно восстановлен.',
        titleTrashed: '{{label}} "{{title}}" перемещен в корзину.',
        trash: 'Мусор',
        trashedCountSuccessfully: '{{count}} {{label}} перемещено в корзину.',
        true: 'Правда',
        unauthorized: 'Нет доступа',
        unlock: 'Разблокировать',
        unsavedChanges: 'У вас есть несохраненные изменения. Сохраните или отмените их перед продолжением.',
        unsavedChangesDuplicate: 'У вас есть несохраненные изменения. Вы хотите продолжить дублирование?',
        untitled: 'Без названия',
        upcomingEvents: 'Предстоящие события',
        updatedAt: 'Дата правки',
        updatedCountSuccessfully: 'Обновлено {{count}} {{label}} успешно.',
        updatedLabelSuccessfully: 'Успешно обновлено {{label}}.',
        updatedSuccessfully: 'Успешно Обновлено.',
        updateForEveryone: 'Обновление для всех',
        updating: 'Обновление',
        uploading: 'Загрузка',
        uploadingBulk: 'Загрузка {{current}} из {{total}}',
        user: 'пользователь',
        username: 'Имя пользователя',
        users: 'пользователи',
        value: 'Значение',
        viewing: 'Просмотр',
        viewReadOnly: 'Просмотр только для чтения',
        welcome: 'Добро пожаловать',
        yes: 'Да'
    },
    localization: {
        cannotCopySameLocale: 'Невозможно скопировать в ту же локаль',
        copyFrom: 'Скопировать из',
        copyFromTo: 'Копирование из {{from}} в {{to}}',
        copyTo: 'Копировать в',
        copyToLocale: 'Копировать в локаль',
        localeToPublish: 'Локаль для публикации',
        selectedLocales: 'Выбранные локали',
        selectLocaleToCopy: 'Выберите локаль для копирования',
        selectLocaleToDuplicate: 'Выберите локали для дублирования'
    },
    operators: {
        contains: 'содержит',
        equals: 'равно',
        exists: 'существует',
        intersects: 'пересекает',
        isGreaterThan: 'больше чем',
        isGreaterThanOrEqualTo: 'больше или равно',
        isIn: 'находится',
        isLessThan: 'меньше чем',
        isLessThanOrEqualTo: 'меньше или равно',
        isLike: 'похоже',
        isNotEqualTo: 'не равно',
        isNotIn: 'нет в',
        isNotLike: 'не похож',
        near: 'рядом',
        within: 'в пределах'
    },
    upload: {
        addFile: 'Добавить файл',
        addFiles: 'Добавить файлы',
        bulkUpload: 'Массовая загрузка',
        crop: 'Обрезать',
        cropToolDescription: 'Перетащите углы выбранной области, нарисуйте новую область или отрегулируйте значения ниже.',
        download: 'Скачать',
        dragAndDrop: 'Перетащите файл',
        dragAndDropHere: 'или перетащите файл сюда',
        editImage: 'Редактировать изображение',
        fileName: 'Имя файла',
        fileSize: 'Размер файла',
        filesToUpload: 'Файлы для загрузки',
        fileToUpload: 'Файл для загрузки',
        focalPoint: 'Центральная точка',
        focalPointDescription: 'Перетащите фокусное расстояние прямо на предварительный просмотр или отрегулируйте значения ниже.',
        height: 'Высота',
        lessInfo: 'Меньше информации',
        moreInfo: 'Больше информации',
        noFile: 'Нет файла',
        pasteURL: 'Вставить URL',
        previewSizes: 'Предварительный просмотр размеров',
        selectCollectionToBrowse: 'Выберите Коллекцию для просмотра',
        selectFile: 'Выберите файл',
        setCropArea: 'Установите область обрезки',
        setFocalPoint: 'Установить фокусное расстояние',
        sizes: 'Размеры',
        sizesFor: 'Размеры для {{label}}',
        width: 'Ширина'
    },
    validation: {
        emailAddress: 'Пожалуйста, введите корректный адрес email.',
        enterNumber: 'Пожалуйста, введите корректный номер.',
        fieldHasNo: 'У этого поля нет {{label}}',
        greaterThanMax: '{{value}} больше максимально допустимого значения {{label}} {{max}}.',
        invalidBlock: 'Блок "{{block}}" не разрешен.',
        invalidBlocks: 'В этом поле содержатся блоки, которые больше не разрешены: {{blocks}}.',
        invalidInput: 'Это поле имеет недопустимое значение.',
        invalidSelection: 'В этом поле выбран недопустимый вариант.',
        invalidSelections: "'Это поле содержит следующие неправильные варианты:'",
        latitudeOutOfBounds: 'Широта должна быть между -90 и 90.',
        lessThanMin: '{{value}} меньше минимально допустимого значения {{label}} {{min}}.',
        limitReached: 'Достигнут лимит, можно добавить только {{max}} элементов.',
        longerThanMin: 'Это значение должно быть больше минимальной длины символов: {{minLength}}.',
        longitudeOutOfBounds: 'Долгота должна быть между -180 и 180.',
        notValidDate: '"{{value}}" это не действительная дата.',
        required: 'Это обязательное поле.',
        requiresAtLeast: 'Это поле требует не менее {{count}} {{label}}',
        requiresNoMoreThan: 'Это поле требует не более {{count}} {{label}}',
        requiresTwoNumbers: 'В этом поле требуется два числа.',
        shorterThanMax: 'Это значение должно быть короче максимальной длины символов {{maxLength}}.',
        timezoneRequired: 'Требуется указать часовой пояс.',
        trueOrFalse: 'Это поле может быть равно только true или false.',
        username: 'Пожалуйста, введите действительное имя пользователя. Может содержать буквы, цифры, дефисы, точки и подчёркивания.',
        validUploadID: "'Это поле не является действительным ID загрузки.'"
    },
    version: {
        type: 'Тип',
        aboutToPublishSelection: 'Вы собираетесь опубликовать все {{label}} в выборе. Вы уверены?',
        aboutToRestore: 'Вы собираетесь восстановить этот документ {{label}} в состояние, в котором он находился {{versionDate}}.',
        aboutToRestoreGlobal: 'Вы собираетесь восстановить глобальную запись {{label}} в состояние, в котором она находилась {{versionDate}}.',
        aboutToRevertToPublished: 'Вы собираетесь вернуть изменения этого документа к его опубликованному состоянию. Вы уверены?',
        aboutToUnpublish: 'Вы собираетесь отменить публикацию этого документа. Вы уверены?',
        aboutToUnpublishIn: 'Вы собираетесь снять с публикации этот документ на {{locale}}. Вы уверены?',
        aboutToUnpublishSelection: 'Вы собираетесь отменить публикацию всех выбранных {{label}}. Вы уверены?',
        autosave: 'Автосохранение',
        autosavedSuccessfully: 'Автосохранение успешно.',
        autosavedVersion: 'Автоматически сохраненная версия',
        changed: 'Изменено',
        changedFieldsCount_one: '{{count}} изменил поле',
        changedFieldsCount_other: '{{count}} измененных полей',
        compareVersion: 'Сравнить версию с:',
        compareVersions: 'Сравнить версии',
        comparingAgainst: 'Сравнивая с',
        confirmPublish: 'Подтвердить публикацию',
        confirmRevertToSaved: 'Подтвердить возврат к сохраненному',
        confirmUnpublish: 'Подтвердить отмену публикации',
        confirmVersionRestoration: 'Подтвердить восстановление версии',
        currentDocumentStatus: 'Текущий статус {{docStatus}} документа',
        currentDraft: 'Текущий проект',
        currentlyPublished: 'В настоящее время опубликовано',
        currentlyViewing: 'В настоящее время просматривается',
        currentPublishedVersion: 'Текущая опубликованная версия',
        draft: 'Черновик',
        draftHasPublishedVersion: 'Черновик (имеет опубликованную версию)',
        draftSavedSuccessfully: 'Черновик успешно сохранен.',
        lastSavedAgo: 'Последний раз сохранено {{distance}} назад',
        modifiedOnly: 'Модифицирован только',
        moreVersions: 'Больше версий...',
        noFurtherVersionsFound: 'Другие версии не найдены',
        noLabelGroup: 'Неименованная Группа',
        noRowsFound: 'Не найдено {{label}}',
        noRowsSelected: 'Не выбран {{label}}',
        preview: 'Предпросмотр',
        previouslyDraft: 'Ранее был черновик',
        previouslyPublished: 'Ранее опубликовано',
        previousVersion: 'Предыдущая версия',
        problemRestoringVersion: 'Возникла проблема с восстановлением этой версии',
        publish: 'Публиковать',
        publishAllLocales: 'Опубликовать все локали',
        publishChanges: 'Опубликовать изменения',
        published: 'Опубликовано',
        publishIn: 'Опубликовать на {{locale}}',
        publishing: 'Публикация',
        restoreAsDraft: 'Восстановить как черновик',
        restoredSuccessfully: 'Восстановлен успешно.',
        restoreThisVersion: 'Восстановить эту версию',
        restoring: 'Восстановление...',
        reverting: 'Возврат...',
        revertToPublished: 'Вернуться к опубликованному',
        revertUnsuccessful: 'Откат не удался. Ранее опубликованная версия не найдена.',
        saveDraft: 'Сохранить черновик',
        scheduledSuccessfully: 'Успешно запланировано.',
        schedulePublish: 'Планирование публикации',
        selectLocales: 'Выберите локали для отображения',
        selectVersionToCompare: 'Выбрать версию для сравнения',
        showingVersionsFor: 'Показаны версии для:',
        showLocales: 'Показать локали:',
        specificVersion: 'Конкретная версия',
        status: 'Статус',
        unpublish: 'Отменить публикацию',
        unpublished: 'Неопубликованный',
        unpublishedSuccessfully: 'Успешно снято с публикации.',
        unpublishIn: 'Отменить публикацию на {{locale}}',
        unpublishing: 'Отмена публикации...',
        version: 'Версия',
        versionAgo: '{{distance}} назад',
        versionCount_many: '{{count}} версий найдено',
        versionCount_none: 'Версий не найдено',
        versionCount_one: '{{count}} версия найдена',
        versionCount_other: 'Найдено {{count}} версий',
        versionID: 'ID версии',
        versions: 'Версии',
        viewingVersion: 'Просмотр версии для {{entityLabel}} {{documentTitle}}',
        viewingVersionGlobal: '`Просмотр версии для глобальной Коллекции {{entityLabel}}',
        viewingVersions: 'Просмотр версий для {{entityLabel}} {{documentTitle}}',
        viewingVersionsGlobal: '`Просмотр версии для глобальной Коллекции {{entityLabel}}'
    }
};
const ru = {
    dateFNSKey: 'ru',
    translations: ruTranslations
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/addFieldStatePromise.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "addFieldStatePromise",
    ()=>addFieldStatePromise
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$resolveFilterOptions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/resolveFilterOptions.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/isRowCollapsed.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
;
;
;
;
;
const ObjectId = 'default' in __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"] ? __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"].default : __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$bson$2d$objectid$2f$objectid$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"];
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
                        acc.promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                        const isCollapsed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isRowCollapsed"])({
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
                            acc.promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                            const isCollapsed = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$isRowCollapsed$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isRowCollapsed"])({
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
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                            const query = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$utilities$2f$resolveFilterOptions$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["resolveFilterOptions"])(field.filterOptions, {
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
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
        return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/index.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "calculateDefaultValues",
    ()=>calculateDefaultValues
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
const calculateDefaultValues = async ({ id, data, fields, locale, req, select, selectMode, user })=>{
    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "iterateFields",
    ()=>iterateFields
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/promise.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
;
const iterateFields = async ({ id, data, fields, locale, req, select, selectMode, siblingData, user })=>{
    const promises = [];
    fields.forEach((field)=>{
        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$promise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["defaultValuePromise"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/promise.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "defaultValuePromise",
    ()=>defaultValuePromise
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/iterateFields.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
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
                        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                            promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/index.js [app-rsc] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "fieldSchemasToFormState",
    ()=>fieldSchemasToFormState
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/calculateDefaultValues/index.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
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
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$calculateDefaultValues$2f$index$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["calculateDefaultValues"])({
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
        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$iterateFields$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["iterateFields"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/isRowCollapsed.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/iterateFields.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

return __turbopack_context__.a(async (__turbopack_handle_async_dependencies__, __turbopack_async_result__) => { try {
__turbopack_context__.s([
    "iterateFields",
    ()=>iterateFields
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload [external] (payload, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__ = __turbopack_context__.i("[externals]/payload/shared [external] (payload/shared, esm_import, [project]/blueprints/payload-next-multisite/app/node_modules/payload)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/forms/fieldSchemasToFormState/addFieldStatePromise.js [app-rsc] (ecmascript)");
var __turbopack_async_dependencies__ = __turbopack_handle_async_dependencies__([
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__
]);
[__TURBOPACK__imported__module__$5b$externals$5d2f$payload__$5b$external$5d$__$28$payload$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$externals$5d2f$payload$2f$shared__$5b$external$5d$__$28$payload$2f$shared$2c$__esm_import$2c$__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$29$__, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__] = __turbopack_async_dependencies__.then ? (await __turbopack_async_dependencies__)() : __turbopack_async_dependencies__;
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
        promises.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$forms$2f$fieldSchemasToFormState$2f$addFieldStatePromise$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["addFieldStatePromise"])({
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/buildFieldSchemaMap/traverseFields.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/utilities/resolveFilterOptions.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
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
"[project]/blueprints/payload-next-multisite/app/node_modules/@swc/helpers/cjs/_interop_require_wildcard.cjs [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

function _getRequireWildcardCache(nodeInterop) {
    if (typeof WeakMap !== "function") return null;
    var cacheBabelInterop = new WeakMap();
    var cacheNodeInterop = new WeakMap();
    return (_getRequireWildcardCache = function(nodeInterop) {
        return nodeInterop ? cacheNodeInterop : cacheBabelInterop;
    })(nodeInterop);
}
function _interop_require_wildcard(obj, nodeInterop) {
    if (!nodeInterop && obj && obj.__esModule) return obj;
    if (obj === null || typeof obj !== "object" && typeof obj !== "function") return {
        default: obj
    };
    var cache = _getRequireWildcardCache(nodeInterop);
    if (cache && cache.has(obj)) return cache.get(obj);
    var newObj = {
        __proto__: null
    };
    var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor;
    for(var key in obj){
        if (key !== "default" && Object.prototype.hasOwnProperty.call(obj, key)) {
            var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null;
            if (desc && (desc.get || desc.set)) Object.defineProperty(newObj, key, desc);
            else newObj[key] = obj[key];
        }
    }
    newObj.default = obj;
    if (cache) cache.set(obj, newObj);
    return newObj;
}
exports._ = _interop_require_wildcard;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/bson-objectid/objectid.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {

var MACHINE_ID = Math.floor(Math.random() * 0xFFFFFF);
var index = ObjectID.index = parseInt(Math.random() * 0xFFFFFF, 10);
var pid = (typeof process === 'undefined' || typeof process.pid !== 'number' ? Math.floor(Math.random() * 100000) : process.pid) % 0xFFFF;
// <https://github.com/williamkapke/bson-objectid/pull/51>
// Attempt to fallback Buffer if _Buffer is undefined (e.g. for Node.js).
// Worst case fallback to null and handle with null checking before using.
var BufferCtr = (()=>{
    try {
        return _Buffer;
    } catch (_) {
        try {
            return Buffer;
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
"[project]/blueprints/payload-next-multisite/app/node_modules/escape-html/index.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

/*!
 * escape-html
 * Copyright(c) 2012-2013 TJ Holowaychuk
 * Copyright(c) 2015 Andreas Lubbe
 * Copyright(c) 2015 Tiancheng "Timothy" Gu
 * MIT Licensed
 */ /**
 * Module variables.
 * @private
 */ var matchHtmlRegExp = /["'&<>]/;
/**
 * Module exports.
 * @public
 */ module.exports = escapeHtml;
/**
 * Escape special characters in the given string of html.
 *
 * @param  {string} string The string to escape for inserting into HTML
 * @return {string}
 * @public
 */ function escapeHtml(string) {
    var str = '' + string;
    var match = matchHtmlRegExp.exec(str);
    if (!match) {
        return str;
    }
    var escape;
    var html = '';
    var index = 0;
    var lastIndex = 0;
    for(index = match.index; index < str.length; index++){
        switch(str.charCodeAt(index)){
            case 34:
                escape = '&quot;';
                break;
            case 38:
                escape = '&amp;';
                break;
            case 39:
                escape = '&#39;';
                break;
            case 60:
                escape = '&lt;';
                break;
            case 62:
                escape = '&gt;';
                break;
            default:
                continue;
        }
        if (lastIndex !== index) {
            html += str.substring(lastIndex, index);
        }
        lastIndex = index + 1;
        html += escape;
    }
    return lastIndex !== index ? html + str.substring(lastIndex, index) : html;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/native.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/node:crypto [external] (node:crypto, cjs)");
;
const __TURBOPACK__default__export__ = {
    randomUUID: __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__["randomUUID"]
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/regex.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
const __TURBOPACK__default__export__ = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$/i;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/rng.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>rng
]);
var __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__ = __turbopack_context__.i("[externals]/node:crypto [external] (node:crypto, cjs)");
;
const rnds8Pool = new Uint8Array(256);
let poolPtr = rnds8Pool.length;
function rng() {
    if (poolPtr > rnds8Pool.length - 16) {
        (0, __TURBOPACK__imported__module__$5b$externals$5d2f$node$3a$crypto__$5b$external$5d$__$28$node$3a$crypto$2c$__cjs$29$__["randomFillSync"])(rnds8Pool);
        poolPtr = 0;
    }
    return rnds8Pool.slice(poolPtr, poolPtr += 16);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/stringify.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "unsafeStringify",
    ()=>unsafeStringify
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$validate$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/validate.js [app-rsc] (ecmascript)");
;
const byteToHex = [];
for(let i = 0; i < 256; ++i){
    byteToHex.push((i + 0x100).toString(16).slice(1));
}
function unsafeStringify(arr, offset = 0) {
    return (byteToHex[arr[offset + 0]] + byteToHex[arr[offset + 1]] + byteToHex[arr[offset + 2]] + byteToHex[arr[offset + 3]] + '-' + byteToHex[arr[offset + 4]] + byteToHex[arr[offset + 5]] + '-' + byteToHex[arr[offset + 6]] + byteToHex[arr[offset + 7]] + '-' + byteToHex[arr[offset + 8]] + byteToHex[arr[offset + 9]] + '-' + byteToHex[arr[offset + 10]] + byteToHex[arr[offset + 11]] + byteToHex[arr[offset + 12]] + byteToHex[arr[offset + 13]] + byteToHex[arr[offset + 14]] + byteToHex[arr[offset + 15]]).toLowerCase();
}
function stringify(arr, offset = 0) {
    const uuid = unsafeStringify(arr, offset);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$validate$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"])(uuid)) {
        throw TypeError('Stringified UUID is invalid');
    }
    return uuid;
}
const __TURBOPACK__default__export__ = stringify;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/v4.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$native$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/native.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$rng$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/rng.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$stringify$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/stringify.js [app-rsc] (ecmascript)");
;
;
;
function _v4(options, buf, offset) {
    options = options || {};
    const rnds = options.random ?? options.rng?.() ?? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$rng$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"])();
    if (rnds.length < 16) {
        throw new Error('Random bytes length must be >= 16');
    }
    rnds[6] = rnds[6] & 0x0f | 0x40;
    rnds[8] = rnds[8] & 0x3f | 0x80;
    if (buf) {
        offset = offset || 0;
        if (offset < 0 || offset + 16 > buf.length) {
            throw new RangeError(`UUID byte range ${offset}:${offset + 15} is out of buffer bounds`);
        }
        for(let i = 0; i < 16; ++i){
            buf[offset + i] = rnds[i];
        }
        return buf;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$stringify$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["unsafeStringify"])(rnds);
}
function v4(options, buf, offset) {
    if (__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$native$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"].randomUUID && !buf && !options) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$native$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"].randomUUID();
    }
    return _v4(options, buf, offset);
}
const __TURBOPACK__default__export__ = v4;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/v4.js [app-rsc] (ecmascript) <export default as v4>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "v4",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$v4$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$v4$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/v4.js [app-rsc] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/validate.js [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$regex$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist-node/regex.js [app-rsc] (ecmascript)");
;
function validate(uuid) {
    return typeof uuid === 'string' && __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2d$node$2f$regex$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["default"].test(uuid);
}
const __TURBOPACK__default__export__ = validate;
}),
];

//# sourceMappingURL=%5Broot-of-the-server%5D__0qbk_qa._.js.map