/*
Copyright 2023 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/
'use strict'

const DEMO_SOURCE_CODE =
    'https://github.com/GoogleCloudPlatform/document-ai-samples/' +
    'tree/main/' +
    'web-app-pix2info-python'

// Adapt as needed
const DIMENSION_CONSTRAINT = {
    min: 720,
    ideal: 2500, // Rough size at which a sheet of paper can be captured at 300 dpi
}
const CAPTURE_CONSTRAINTS = {
    width: DIMENSION_CONSTRAINT,
    height: DIMENSION_CONSTRAINT,
    // aspectRatio might be interesting (to match the proportions of a sheet of paper)
}

const PDF = 'application/pdf'
const SUPPORTED_TYPES = [
    PDF,
    'image/gif',
    'image/tiff',
    'image/jpeg',
    'image/png',
    'image/bmp',
    'image/webp',
]

const eLocation = document.getElementById('location')
const eProcessor = document.getElementById('processor')
const eCamera = document.getElementById('camera')
const eFiles = document.getElementById('files')
const eSamples = document.getElementById('samples')
const eDialog = document.getElementById('dialog')
const eSnapshot = document.getElementById('snapshot')
const eVideo = document.getElementById('video')
const ePage = document.getElementById('page')
const eOverlay = document.getElementById('overlay')
const eOutputImage = document.getElementById('output-image')
const eDocumentText = document.getElementById('document-text')
const eTree = document.getElementById('document-tree')
const eOptions = document.getElementById('options')
const eSourceCode = document.getElementById('source-code')
const eDownloadDocaiJson = document.getElementById('download-docai-json')
const eDownloadOutputImage = document.getElementById('download-output-image')

// Maps backend's options.ImageFormat (case insensitive, use best case for display)
const OUTPUT_FORMATS = ['Auto', 'WebP', 'PNG', 'GIF']
const DEFAULT_OUTPUT_FORMAT = OUTPUT_FORMATS[0]

// Runtime data
const DOCUMENT_SOURCE_CAMERA = 1
const DOCUMENT_SOURCE_FILES = 2
const DOCUMENT_SOURCE_SAMPLE = 3
const gData = {
    // DOCUMENT_SOURCE_*
    source: null,
    // User input blobs (from camera or local files)
    blobs: null,
    // Output structured document (sent to the backend for the rendering)
    documentJson: null,
    documentSummary: null,
    // Drop effect for ondragover event
    dropEffect: 'none',
}

// User parameters (serialized in Local Storage)
const LOCAL_STORAGE_KEY = 'docaiPixToInfo'
const gParams = {
    apiLocation: null,
    processorName: null, // Display name
    processorInfo: null, // Opaque string returned by backend
}

const LAZY_LOAD_TREE = true // Memory consumption too high otherwise
const MAX_TREE_ITEM_LEN = 70

class Sample {
    constructor(processor, name, paths) {
        this.processor = processor
        this.name = name
        this.paths = paths
    }
}

// Backend API

async function callApi(url, formData = null) {
    const init = formData
        ? { method: 'POST', body: formData }
        : { method: 'GET' }
    try {
        const t1 = performance.now()

        const response = await fetch(url, init)
        if (response.status != 200) {
            console.error(await response.text())
            return null
        }

        const t2 = performance.now()
        console.log(`← ${url} (${Math.round(t2 - t1)} ms)`)
        return response
    } catch (error) {
        console.error(error)
        return null
    }
}

async function textFromApi(url, formData = null) {
    const response = await callApi(url, formData)
    return response ? response.text() : null
}

async function jsonFromApi(url, formData = null) {
    const response = await callApi(url, formData)
    return response ? response.json() : null
}

async function blobFromApi(url, formData = null) {
    const response = await callApi(url, formData)
    return response ? response.blob() : null
}

async function getSamples() {
    return jsonFromApi('/api/samples')
}

async function getLocations() {
    return jsonFromApi('/api/processors/locations')
}

async function getProcessors() {
    const url = `/api/processors/${gParams.apiLocation}`
    return jsonFromApi(url)
}

async function getSampleAnalysis(sample) {
    const url = `/api/analysis/sample/${sample.processor}/${sample.name}`
    const formData = new FormData()
    addPaths(formData, sample.paths)
    return jsonFromApi(url, formData)
}

async function getProcessorAnalysis() {
    const url = `/api/analysis/processor/${gParams.processorInfo}`
    const formData = new FormData()
    addBlobs(formData)
    return jsonFromApi(url, formData)
}

async function renderDocument() {
    const url = '/api/document/render'
    const formData = new FormData()
    if (!addDocument(formData)) return null
    addOptions(formData)
    return blobFromApi(url, formData)
}

function addPaths(formData, paths) {
    for (const path of paths) formData.append('paths[]', path)
}

function addBlobs(formData) {
    for (const blob of gData.blobs) formData.append('blobs[]', blob)
}

function addDocument(formData) {
    if (!gData.documentJson) {
        console.error('No documentJson: cannot continue')
        return false
    }
    formData.append('document_json', gData.documentJson)
    return true
}

function addOptions(formData) {
    const value = (id) => document.getElementById(id).value
    const checked = (value) => elementWithValueIsSelected(value)
    const checked_format = () => {
        for (const f of OUTPUT_FORMATS) if (checked(f)) return f.toLowerCase()
        console.error('No output format is checked')
    }

    // Rendering options: use same fields as backend's options.Options (snake-case NamedTuple)
    const options = {
        page: parseInt(value('page')),
        blocks: checked('blocks'),
        paragraphs: checked('paragraphs'),
        lines: checked('lines'),
        tokens: checked('tokens'),
        tables: checked('tables'),
        fields: checked('fields'),
        entities: checked('entities'),
        barcodes: checked('barcodes'),
        format: checked_format(),
        animated: checked('animated'),
        cropped: checked('cropped'),
        confidence: checked('confidence'),
        normalized: checked('normalized'),
    }
    formData.append('options_json', JSON.stringify(options))
}

// Video/webcam

async function cameraDialog() {
    eCamera.loading = true

    const videoOk = await startVideo()
    if (!videoOk) {
        eCamera.loading = false
        return
    }

    eDialog.show()
}

async function onDialogClosing() {
    stopVideo()

    eCamera.loading = false
}

async function startVideo() {
    try {
        const contraints = { audio: false, video: true }
        const stream = await navigator.mediaDevices.getUserMedia(contraints)
        const track = stream.getVideoTracks()[0]
        await track.applyConstraints(CAPTURE_CONSTRAINTS)
        eVideo.srcObject = stream
        await eVideo.play()
        console.info(`Video res.: ${eVideo.videoWidth}×${eVideo.videoHeight}`)
        return true
    } catch (error) {
        if (error.name === 'OverconstrainedError') {
            console.error(
                `Could not apply constraints: ${JSON.stringify(
                    CAPTURE_CONSTRAINTS
                )}`
            )
        } else {
            console.error(error)
        }
        return false
    }
}

function stopVideo() {
    const stream = eVideo.srcObject
    if (!stream) {
        console.warn(`## No stream`)
        return
    }
    stream.getTracks().forEach((track) => track.stop())
    eVideo.srcObject = null
}

async function snapshot() {
    eVideo.pause()
    const canvas = document.createElement('canvas')
    canvas.width = eVideo.videoWidth
    canvas.height = eVideo.videoHeight
    const contextSettings = { alpha: false } // RGB mode is enough (RGBA by default)
    const context = canvas.getContext('2d', contextSettings)
    context.drawImage(eVideo, 0, 0)
    canvas.toBlob(onCameraBlob, 'image/png')
    eDialog.hide()
}

async function onCameraBlob(blob) {
    await setNewSource(DOCUMENT_SOURCE_CAMERA, [blob])
}

// Files

async function onUserFiles(files) {
    const blobs = []
    for (const file of files) {
        if (!blobs.length || (file.type !== PDF && blobs[0].type !== PDF)) {
            blobs.push(file)
            continue
        }
        console.warn(
            `This demo supports merging images but not PDFs, ignoring ${file.name}`
        )
    }
    if (!blobs.length) return

    await setNewSource(DOCUMENT_SOURCE_FILES, blobs)
}

function selectFiles() {
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.accept = SUPPORTED_TYPES.join(',')
    input.onchange = (ev) => onUserFiles(ev.target.files)
    input.click()
}

async function onDragEnterLeave(event) {
    event.preventDefault()
    switch (event.type) {
        case 'dragenter':
            const files = filterDraggedFiles(event)
            if (0 < files.length) {
                document.body.className = 'drop-zone-active'
                gData.dropEffect = 'copy'
            }
            return
        case 'dragleave':
            if (!event.relatedTarget) {
                document.body.className = ''
                gData.dropEffect = 'none'
            }
            return
    }
}

async function onDragOver(event) {
    event.preventDefault()
    event.dataTransfer.dropEffect = gData.dropEffect
}

async function onFileDrop(event) {
    event.preventDefault()
    document.body.className = ''

    const files = filterDraggedFiles(event)
    await onUserFiles(files)
}

function filterDraggedFiles(event) {
    const files = []

    const dataTransfer = event.dataTransfer
    if (!dataTransfer || !dataTransfer.items) {
        console.error('DataTransfer is not supported')
        return files
    }

    for (const item of dataTransfer.items)
        if (item.kind === 'file' && SUPPORTED_TYPES.includes(item.type))
            files.push(item.getAsFile())

    return files
}

// Data

function loadParams() {
    const key = LOCAL_STORAGE_KEY
    const value = localStorage.getItem(key)
    if (!value) return
    const lsParams = JSON.parse(value)
    for (const [key, value] of Object.entries(lsParams)) gParams[key] = value
}

function saveParams() {
    const key = LOCAL_STORAGE_KEY
    localStorage.setItem(key, JSON.stringify(gParams))
}

async function onLocationChanged(event) {
    gParams.apiLocation = eLocation.value
    saveParams()
    await initProcessors()
}

async function onProcessorChanged(event) {
    gParams.processorName = eProcessor.displayLabel
    gParams.processorInfo = eProcessor.value
    saveParams()

    // Relaunch an analysis if needed
    await setNewSource(gData.source, gData.blobs)
}

async function onSampleSelected(event) {
    const sample = event.target.value
    await analyzeSample(sample)
}

function showProcessing(loading) {
    const button = !gData.blobs
        ? eSamples.parentElement.children[0]
        : gData.source == DOCUMENT_SOURCE_FILES
        ? eFiles
        : eCamera

    button.loading = loading
}

async function analyzeSample(sample) {
    await setNewSource(DOCUMENT_SOURCE_SAMPLE, null)
    showProcessing(true)

    const processorName = sample.processor
    const processors = document.querySelectorAll('#processor>sl-option')
    for (const processor of processors) {
        if (processor.textContent !== processorName) continue
        eProcessor.value = processor.value
        await onProcessorChanged(null)
        break
    }

    const analysis = await getSampleAnalysis(sample)
    await onNewAnalysis(analysis)

    showProcessing(false)
}

async function setNewSource(source, blobs) {
    gData.source = source
    gData.blobs = blobs

    onNewInput()
    if (blobs) await analyseBlobs()
}

function onNewInput() {
    initDocumentInfo()
    initPageMenu()
    initOverlayMenu()
    initOutputImage()
}

async function analyseBlobs() {
    showProcessing(true)

    const analysis = await getProcessorAnalysis()
    await onNewAnalysis(analysis)

    showProcessing(false)
}

async function onNewAnalysis(analysis) {
    if (!analysis) return

    gData.documentJson = analysis.json
    gData.documentSummary = analysis.summary

    await renderOutputImage()
    updateOutputCard()
}

function onOutputOptionSelected(event) {
    const item = event.detail.item
    const value = item.value
    if (item.onclick) return // Event handled differently (e.g. a command menu item)

    if (OUTPUT_FORMATS.includes(value)) {
        if (!item.checked) {
            item.checked = true
            return
        }
        for (const format of OUTPUT_FORMATS)
            if (format !== value) elementWithValue(format).checked = false
    }

    onOutputOptionChanged(null)
}

function onOutputPageChanged(event) {
    updateOutputInfo(parseInt(ePage.value))
    onOutputOptionChanged(null)
}

function onOutputOptionChanged(event) {
    if (!gData.documentJson) return
    renderOutputImage(showProcessing)
}

function updateOutputCard() {
    initDocumentInfo()

    ePage.innerHTML = ''
    const pageCount = gData.documentSummary.counts.pages
    for (let pageIndex = 0; pageIndex < pageCount; ++pageIndex) {
        const option = document.createElement('sl-option')
        option.value = `${pageIndex + 1}`
        option.textContent = `${pageIndex + 1} / ${pageCount}`
        ePage.appendChild(option)
    }

    const defaultPageNumber = 1
    ePage.value = `${defaultPageNumber}`
    ePage.disabled = pageCount < 2

    updateOutputInfo(defaultPageNumber)
}

function updateOutputInfo(pageNumber) {
    const summary = gData.documentSummary
    if (!summary) return

    const pageCount = summary.counts.pages
    for (const [value, counts] of Object.entries(summary.counts)) {
        const element = elementWithValue(value)
        if (!element) continue
        const s = element.textContent
        const i = s.indexOf(' (')
        if (i == -1) continue
        const total = counts[0]
        const count = counts[pageNumber]
        element.textContent =
            1 < pageCount
                ? `${s.slice(0, i)} (${count} / ${total})`
                : `${s.slice(0, i)} (${count})`
    }
}

function elementWithValue(value) {
    return document.querySelector(`[value='${value}']`)
}

function elementWithValueIsSelected(value) {
    const element = elementWithValue(value)
    return element.tagName === 'SL-OPTION'
        ? element.parentElement.value.split().includes(value)
        : element.checked
}

async function renderOutputImage(beforeAfterFunc = null) {
    if (beforeAfterFunc) beforeAfterFunc(true)

    const imageBlob = await renderDocument()
    if (imageBlob) {
        const blobMiB = Math.round((imageBlob.size / (1024 * 1024)) * 10) / 10
        console.log(`← ${imageBlob.type}: ${blobMiB} MiB`)

        URL.revokeObjectURL(eOutputImage.src)
        eOutputImage.src = URL.createObjectURL(imageBlob)

        // Store timed filename in title (useful for potential download from user)
        const fileExt = imageBlob.type.split('/')[1]
        eOutputImage.title = getTimedFilename(fileExt)
        eOutputImage.hidden = false
    }

    if (beforeAfterFunc) beforeAfterFunc(false)
}

// Initialization

function resetParams() {
    gParams.apiLocation = null
    gParams.processorName = null
    gParams.processorInfo = null
}

function initParams() {
    loadParams()
}

function initElements() {
    initDocumentInfo()
    initPageMenu()
    initOverlayMenu()
    initOutputImage()
    initOptionsMenu()
    plugEvents()
}

function initPageMenu() {
    ePage.innerHTML = ''

    const option = document.createElement('sl-option')
    option.textContent = option.value = '1'
    ePage.appendChild(option)
    ePage.value = '1'
    ePage.disabled = true
}

function initOverlayMenu() {
    for (const item of eOverlay.children) {
        const s = item.textContent
        const i = s.indexOf(' (')
        if (i == -1) continue
        item.textContent = `${s.slice(0, i)} (0)`
    }
}

function initOutputImage() {
    eOutputImage.hidden = true
    URL.revokeObjectURL(eOutputImage.src)
    eOutputImage.src = ''
}

function initOptionsMenu() {
    for (const format of OUTPUT_FORMATS) {
        const item = document.createElement('sl-menu-item')
        item.setAttribute('value', format)
        item.setAttribute('type', 'checkbox')
        item.textContent = format
        if (format == DEFAULT_OUTPUT_FORMAT) item.checked = true
        eOptions.appendChild(item)
    }
}

function plugEvents() {
    eCamera.onclick = cameraDialog
    eFiles.onclick = selectFiles

    eLocation.addEventListener('sl-change', onLocationChanged)
    eProcessor.addEventListener('sl-change', onProcessorChanged)

    ePage.addEventListener('sl-change', onOutputPageChanged)
    eOverlay.addEventListener('sl-change', onOutputOptionChanged)
    eOptions.addEventListener('sl-select', onOutputOptionSelected)

    eSourceCode.onclick = viewProjectSourceCode
    eDownloadDocaiJson.onclick = downloadDocaiJson
    eDownloadOutputImage.onclick = downloadOutputImage

    eSnapshot.onclick = snapshot
    eDialog.addEventListener('sl-hide', onDialogClosing)

    document.ondragenter = document.ondragleave = onDragEnterLeave
    document.ondragover = onDragOver
    document.ondrop = onFileDrop
}

function getTimedFilename(fileExtension) {
    const fileDate = new Date().toISOString().split('.')[0]
    return `docaiPixToInfo_${fileDate}.${fileExtension}`
}

function viewProjectSourceCode(event) {
    const link = document.createElement('a')
    link.href = DEMO_SOURCE_CODE
    link.target = '_blank'
    link.click()
}

function downloadDocaiJson(event) {
    if (!gData.documentJson) return

    const link = document.createElement('a')
    link.download = getTimedFilename('json')
    link.href =
        'data:application/json;charset=utf-8,' +
        encodeURIComponent(gData.documentJson)
    link.click()
}

function downloadOutputImage(event) {
    if (eOutputImage.hidden) return

    const link = document.createElement('a')
    link.href = eOutputImage.src
    link.download = eOutputImage.title
    link.click()
}

async function initLocation() {
    eLocation.innerHTML = ''
    const locations = await getLocations()
    if (!locations) return

    let match = false
    for (const location of locations) {
        const option = document.createElement('sl-option')
        option.textContent = option.value = location
        eLocation.appendChild(option)
        if (location == gParams.apiLocation) match = true
    }
    if (!match) gParams.apiLocation = null

    if (!gParams.apiLocation && 0 < locations.length)
        gParams.apiLocation = locations[0]

    if (gParams.apiLocation) {
        eLocation.value = gParams.apiLocation
        await onLocationChanged(null) // Will call initProcessors
    }
}

async function initProcessors() {
    eProcessor.innerHTML = ''
    const processors = await getProcessors()
    if (!processors) return

    let match = null
    for (const [name, proc_info] of Object.entries(processors)) {
        const option = document.createElement('sl-option')
        option.textContent = name
        option.value = proc_info
        eProcessor.appendChild(option)
        // Match by name (keep same processor type if location changes)
        if (gParams.processorName === name) match = option
    }
    if (!match && 0 < eProcessor.children.length) match = eProcessor.children[0]

    gParams.processorName = gParams.processorInfo = null
    saveParams()

    if (match) {
        eProcessor.value = match.value
        await onProcessorChanged(null)
    }
}

async function initSamples() {
    eSamples.innerHTML = ''
    const samples = await getSamples()

    for (const [procName, procSamples] of Object.entries(samples)) {
        if (0 < eSamples.children.length)
            eSamples.appendChild(document.createElement('sl-divider'))
        const label = document.createElement('sl-menu-label')
        label.textContent = procName
        eSamples.appendChild(label)

        for (const [sampleName, samplePaths] of Object.entries(procSamples)) {
            const item = document.createElement('sl-menu-item')
            item.textContent = sampleName
            item.value = new Sample(procName, sampleName, samplePaths)
            const icon = document.createElement('sl-icon')
            icon.slot = 'prefix'
            icon.name = 'file-earmark'
            item.appendChild(icon)
            item.addEventListener('click', onSampleSelected)
            eSamples.appendChild(item)
        }
    }
}

function initDocumentInfo() {
    const treeItem = document.createElement('sl-tree-item')
    treeItem.setAttribute('expanded', true)
    const iconName = gData.documentJson
        ? 'file-earmark-check'
        : 'file-earmark-x'
    treeItem.innerHTML = `<sl-icon name="${iconName}"></sl-icon>document`

    eDocumentText.value = ''
    eDocumentText.disabled = true
    eTree.innerHTML = ''
    eTree.appendChild(treeItem)
    if (!gData.documentJson) return

    const docNode = JSON.parse(gData.documentJson)
    eDocumentText.value = docNode.text.trimEnd().replaceAll('\n', ' ↩️ ')
    eDocumentText.disabled = false
    fillDocumentTree(treeItem, docNode)
}

function fillDocumentTree(treeParent, docNode) {
    for (const [key, value] of Object.entries(docNode)) {
        const treeItem = getTreeItem(key, value)
        if (!treeItem) continue
        treeParent.appendChild(treeItem)
    }
}

function getTreeItem(key, value) {
    if (typeof key !== 'string') {
        console.error(`## ${key} / Key type is not a string: ${typeof key}`)
        return null
    }

    const item = document.createElement('sl-tree-item')
    switch (typeof value) {
        case 'object':
            const isArray = Array.isArray(value)
            item.textContent = isArray ? `${key}[]` : `${key}`
            if (!isArray && !Object.entries(value).length) {
                // Empty object (e.g. a protobuf message with default fields)
                break
            }
            if (LAZY_LOAD_TREE) {
                item.value = value
                item.setAttribute('lazy', true)
                item.addEventListener('sl-lazy-load', lazyLoadTreeItem)
            } else {
                fillDocumentTree(item, value)
            }
            break
        case 'string':
            if (MAX_TREE_ITEM_LEN < value.length)
                value = `${value.slice(0, MAX_TREE_ITEM_LEN)}…`
            value = value.replaceAll('\n', '\\n')
            item.textContent = `${key}: "${value}"`
            break
        case 'number':
        case 'bigint':
            item.textContent = `${key}: ${value}`
            break
        default:
            console.error(`## ${key} / Unhandled value type: ${typeof value}`)
            return null
    }

    return item
}

function lazyLoadTreeItem(event) {
    const treeItem = event.srcElement
    if (!treeItem.lazy) return // Prevent multiple calls
    treeItem.lazy = false

    const docNode = treeItem.value
    treeItem.value = null // Release memory
    fillDocumentTree(treeItem, docNode)
}

async function initApp() {
    initParams()
    initElements()
    initLocation()
    initSamples()
}

initApp()
