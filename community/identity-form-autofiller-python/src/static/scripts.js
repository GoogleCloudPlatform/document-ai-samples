/*
Copyright 2022 Google LLC

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
const VIDEO_CONSTRAINTS = { width: { min: 720 }, height: { min: 720 } }
const BUTTON_PHOTO1 = 'photo1'
const BUTTON_PHOTO2 = 'photo2'
const BUTTON_UPLOAD = 'upload'
const BUTTON_PROCESS = 'process'
const BUTTON_RESET = 'reset'
const BUTTON_SNAPSHOT = 'snapshot'
const eLocation = document.getElementById('user-location')
const eProcessor = document.getElementById('user-processor')
const eSamples = document.getElementById('samples')
const eProcess = document.getElementById(BUTTON_PROCESS)
const eForm = document.getElementById('user-form')
const eFormOptions = document.getElementById('form-options')
const eShowConfidence = document.getElementById('show-confidence')
const eShowPageNumbers = document.getElementById('show-page-numbers')
const eShowNormalizedValues = document.getElementById('show-normalized-values')
const eDialog = document.getElementById('dialog')
const eVideo = document.getElementById('video')
const GPARAMS_LS_KEY = 'gParams'
const gParams = {
    projectId: null,
    apiLocation: null,
    processorData: null,
    showConfidence: false,
    showPageNumbers: false,
    showNormalized: false,
}
const MAX_RIGHT_ALIGNED_LABEL_CHARS = 15
const gPhotoMaxCount = 2
let gPhotoIndex = 0 // 0 <= gPhotoIndex < gPhotoMaxCount
let gImageFields = []
let gAnalysis = null
let gDropEffect = 'none'

// API

async function jsonFromApi(url, init) {
    try {
        const response = await fetch(url, init)
        if (!response.ok) {
            if (response.status == 400) console.error(await response.text())
            return null
        }
        return response.json()
    } catch (error) {
        console.error(error)
        return null
    }
}

async function getSamples() {
    const url = '/api/samples'
    const init = { method: 'GET' }
    const response = await jsonFromApi(url, init)

    return response ? response.samples : null
}

async function getProjectId() {
    const url = '/api/project'
    const init = { method: 'GET' }
    const response = await jsonFromApi(url, init)

    return response ? response.project : null
}

async function getLocations() {
    const url = '/api/processors/locations'
    const init = { method: 'GET' }
    const response = await jsonFromApi(url, init)

    return response ? response.locations : null
}

async function getProcessors() {
    const url = `/api/processors/${gParams.projectId}/${gParams.apiLocation}`
    const init = { method: 'GET' }
    const response = await jsonFromApi(url, init)

    return response ? response.processors : null
}

async function getProcessorFields() {
    const url = `/api/processor/fields/${gParams.processorData}`
    const init = { method: 'GET' }
    const response = await jsonFromApi(url, init)

    return response ? response.fields : null
}

async function getProcessorAnalysis() {
    const url = `/api/processor/analysis/${gParams.processorData}`
    const init = { method: 'POST', body: await getFormData() }
    const response = await jsonFromApi(url, init)

    return response ? response.analysis : null
}

async function getFormData() {
    const formData = new FormData()

    for (let i = 0; i < gPhotoMaxCount; ++i) {
        const avatar = document.getElementById(`avatar${i + 1}`)
        if (!avatar || !avatar.image) continue
        const response = await fetch(avatar.image)
        const blob = await response.blob()
        formData.append('photos[]', blob)
    }

    return formData
}

// Processing

async function process() {
    await onProcessStart()
    gAnalysis = await getProcessorAnalysis()
    await onProcessEnd()
}

async function onProcessStart() {
    eProcess.loading = true
}

async function onProcessEnd() {
    eProcess.loading = false
    if (!gAnalysis) {
        console.warn('## Empty analysis')
        return
    }

    console.table(gAnalysis)
    updateForm()
}

async function updateForm() {
    for (const [field, pages] of Object.entries(gAnalysis)) {
        const element = document.getElementById(field)
        if (!element) continue

        const isImage = gImageFields.includes(field)
        let confidences = []
        let values = []
        for (let i = 0; i < gPhotoMaxCount; ++i) {
            if (!(i in pages)) continue
            const page = pages[i]

            const page_confidence =
                0 <= parseInt(page.confidence) ? page.confidence : '-'
            confidences.push(`${page_confidence}%`)

            const page_value =
                gParams.showNormalized && page.normalized
                    ? `📐 ${page.normalized}`
                    : page.value
            if (!isImage && gParams.showPageNumbers) {
                const prefix = integerToSymbolEmojis(i + 1)
                values.push(`${prefix} ${page_value}`)
            } else values.push(page_value)
        }

        const label = gParams.showConfidence
            ? `${field} (${confidences.join('/')})`
            : field
        if (isImage) {
            element.label.textContent = label
            element.image = values[0]
        } else {
            const value = values.join(' ➕ ')
            element.label = label
            element.value = value.replaceAll('\n', ' ↩️ ')
        }
    }

    eFormOptions.hidden = false
}

function integerToSymbolEmojis(i) {
    const emojis = ['0️⃣', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    let s = ''

    do {
        s = emojis[i % 10] + s
        i = Math.floor(i / 10)
    } while (0 < i)

    return s
}

async function reset() {
    document.querySelectorAll('sl-input').forEach(resetInput)
    // Reset tooltip first (they use the same image as the avatars)
    document.querySelectorAll('sl-tooltip').forEach(resetTooltip)
    document.querySelectorAll('sl-tooltip>img').forEach(resetTooltipImage)
    // Then reset the avatars
    document.querySelectorAll('sl-avatar').forEach(resetAvatar)
    eFormOptions.hidden = true
}

function resetInput(input) {
    input.value = ''

    // Reset the input label if it was updated with confidence ('FIELD (conf%)')
    const confidenceIndex = input.label.indexOf(' (')
    if (confidenceIndex != -1)
        input.label = input.label.slice(0, confidenceIndex)
}

function resetAvatar(avatar) {
    if (avatar.image) URL.revokeObjectURL(avatar.image)
    avatar.image = ''
    if (!avatar.label) return

    // Reset the avatar label if it was updated with confidence ('FIELD (conf%)')
    const confidenceIndex = avatar.label.textContent.indexOf(' (')
    if (confidenceIndex != -1)
        avatar.label.textContent = avatar.label.textContent.slice(
            0,
            confidenceIndex
        )
}

function resetTooltip(tooltip) {
    tooltip.disabled = true
}

function resetTooltipImage(img) {
    img.src = ''
}

function resetAvatarFromIndex(index) {
    const avatar = snapshotAvatar(index)
    resetAvatar(avatar)

    const tooltip = avatarTooltip(index)
    resetTooltip(tooltip)

    return avatar
}

function currentPhotoButton() {
    const buttonId = `photo${gPhotoIndex + 1}`
    return document.getElementById(buttonId)
}

function snapshotAvatar(index) {
    const avatarId = `avatar${index + 1}`
    return document.getElementById(avatarId)
}

function avatarTooltip(index) {
    const id = `tooltip${index + 1}`
    return document.getElementById(id)
}

function avatarZoomImage(index) {
    const id = `zoom${index + 1}`
    return document.getElementById(id)
}

function updateCurrentSnapshotWithBlob(blob) {
    updateSnapshotWithBlob(gPhotoIndex, blob)
}

function updateSnapshotWithBlob(index, blob) {
    const avatar = resetAvatarFromIndex(index)
    avatar.image = URL.createObjectURL(blob)
    updateAvatarZoom(avatar, index)
}

function updateSnapshotWithSample(index, filename) {
    const avatar = resetAvatarFromIndex(index)
    if (filename) avatar.image = `/api/samples/${filename}`
    updateAvatarZoom(avatar, index)
}

function updateAvatarZoom(avatar, index) {
    const tooltip = avatarTooltip(index)
    const img = avatarZoomImage(index)
    img.src = avatar.image
    tooltip.disabled = false
}

// Video/webcam

async function photoDialog(photoIndex) {
    gPhotoIndex = photoIndex
    const button = currentPhotoButton()
    button.loading = true

    if (!(await startVideo())) {
        button.loading = false
        return
    }

    eDialog.show()
}

async function onDialogClosing() {
    stopVideo()

    const button = currentPhotoButton()
    button.loading = false
}

async function startVideo() {
    try {
        const contraints = { audio: false, video: VIDEO_CONSTRAINTS }
        const stream = await navigator.mediaDevices.getUserMedia(contraints)
        eVideo.srcObject = stream
        await eVideo.play()
        console.info(
            `Video resolution: ${eVideo.videoWidth}×${eVideo.videoHeight}`
        )
        return true
    } catch (error) {
        console.error(error)
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
    const context = canvas.getContext('2d', { alpha: false })
    context.drawImage(eVideo, 0, 0)
    canvas.toBlob(onPhotoBlob)
}

async function onPhotoBlob(blob) {
    if (gPhotoIndex == 0) reset() // Reset only for the first page (let users add other pages)

    updateCurrentSnapshotWithBlob(blob)
    eDialog.hide()
}

// Files

function onUserFiles(files) {
    reset()

    let index = 0
    for (const file of files) {
        if (gPhotoMaxCount <= index) break
        updateSnapshotWithBlob(index, file)
        ++index
    }
}

function selectFiles() {
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.accept = 'image/*'
    input.onchange = (ev) => {
        if (1 <= ev.target.files.length) onUserFiles(ev.target.files)
    }
    input.click()
}

function onDragEnterLeave(event) {
    event.preventDefault()
    switch (event.type) {
        case 'dragenter':
            const files = filterDraggedFiles(event)
            if (0 < files.length) {
                document.body.className = 'drop-zone-active'
                gDropEffect = 'copy'
            }
            return
        case 'dragleave':
            if (!event.relatedTarget) {
                document.body.className = ''
                gDropEffect = 'none'
            }
            return
    }
}

function onDragOver(event) {
    event.preventDefault()
    event.dataTransfer.dropEffect = gDropEffect
}

function onFileDrop(event) {
    event.preventDefault()
    document.body.className = ''

    const files = filterDraggedFiles(event)
    onUserFiles(files)
}

function filterDraggedFiles(event) {
    const files = []

    const dataTransfer = event.dataTransfer
    if (!dataTransfer || !dataTransfer.items) {
        console.error('DataTransfer is not supported')
        return files
    }

    let index = 0
    for (const item of dataTransfer.items) {
        if (gPhotoMaxCount <= index++) break
        console.table(item)
        if (item.kind != 'file' || !item.type.startsWith('image/')) continue
        files.push(item.getAsFile())
    }

    return files
}

// Data

function loadParams() {
    const key = localStorageKeyForParam(GPARAMS_LS_KEY)
    const value = localStorage.getItem(key)
    if (!value) return
    const lsParams = JSON.parse(value)
    for (const [key, value] of Object.entries(lsParams)) gParams[key] = value
}

function saveParams() {
    const key = localStorageKeyForParam(GPARAMS_LS_KEY)
    localStorage.setItem(key, JSON.stringify(gParams))
}

function localStorageKeyForParam(param) {
    return `docaiIdAutofiller-${param}`
}

function onLocationChanged(event) {
    gParams.apiLocation = eLocation.value
    saveParams()
    initProcessors()
}

function onProcessorChanged(event) {
    gParams.processorData = eProcessor.value
    saveParams()
    initForm()
}

function onSampleClick(event) {
    reset()

    const sampleFiles = event.target.value

    for (let i = 0; i < gPhotoMaxCount; ++i) resetAvatarFromIndex(i)

    const limit = Math.min(sampleFiles.length, gPhotoMaxCount)
    for (let i = 0; i < limit; ++i) updateSnapshotWithSample(i, sampleFiles[i])
}

function onShowOptionChanged(event) {
    gParams.showConfidence = eShowConfidence.checked
    gParams.showPageNumbers = eShowPageNumbers.checked
    gParams.showNormalized = eShowNormalizedValues.checked
    saveParams()
    if (gAnalysis) updateForm()
}

// Initialization

async function initParams() {
    loadParams()
    if (gParams.projectId) return
    gParams.projectId = await getProjectId()
}

async function initElements() {
    const buttonFunctions = {
        [BUTTON_PHOTO1]: (_) => photoDialog(0),
        [BUTTON_PHOTO2]: (_) => photoDialog(1),
        [BUTTON_SNAPSHOT]: snapshot,
        [BUTTON_UPLOAD]: selectFiles,
        [BUTTON_PROCESS]: process,
        [BUTTON_RESET]: reset,
    }
    for (const [buttonId, buttonFunction] of Object.entries(buttonFunctions)) {
        const button = document.getElementById(buttonId)
        if (!button) continue
        button.onclick = buttonFunction
    }

    eLocation.addEventListener('sl-change', onLocationChanged)
    eProcessor.addEventListener('sl-change', onProcessorChanged)
    eShowConfidence.checked = gParams.showConfidence
    eShowPageNumbers.checked = gParams.showPageNumbers
    eShowNormalizedValues.checked = gParams.showNormalized
    eShowConfidence.addEventListener('sl-change', onShowOptionChanged)
    eShowPageNumbers.addEventListener('sl-change', onShowOptionChanged)
    eShowNormalizedValues.addEventListener('sl-change', onShowOptionChanged)
    eDialog.addEventListener('sl-hide', onDialogClosing)

    document.ondragenter = document.ondragleave = onDragEnterLeave
    document.ondragover = onDragOver
    document.ondrop = onFileDrop
}

async function initLocation() {
    eLocation.innerHTML = ''
    const locations = await getLocations()
    if (!locations) return

    let match = false
    for (const location of locations) {
        const item = document.createElement('sl-menu-item')
        item.value = item.textContent = location
        eLocation.appendChild(item)
        if (gParams.apiLocation == location) match = true
    }

    if (!match) gParams.apiLocation = null
    if (!gParams.apiLocation && 0 < locations.length)
        gParams.apiLocation = locations[0]
    if (gParams.apiLocation) eLocation.value = gParams.apiLocation
}

async function initProcessors() {
    eProcessor.innerHTML = ''
    const processors = await getProcessors()
    if (!processors) return

    let match = false
    for (const [name, proc_data] of Object.entries(processors)) {
        const item = document.createElement('sl-menu-item')
        item.value = proc_data
        item.textContent = name
        eProcessor.appendChild(item)
        if (gParams.processorData == proc_data) match = true
    }

    if (!match) gParams.processorData = null
    if (!gParams.processorData && 0 < eProcessor.children.length)
        gParams.processorData = eProcessor.children[0].value
    if (gParams.processorData) eProcessor.value = gParams.processorData
}

async function initSamples() {
    eSamples.innerHTML = ''
    const samples = await getSamples()

    for (const [sampleName, samplefiles] of Object.entries(samples)) {
        const item = document.createElement('sl-menu-item')
        item.addEventListener('click', onSampleClick)
        item.value = samplefiles
        item.textContent = sampleName
        eSamples.appendChild(item)
    }
}

async function initForm() {
    gImageFields = []
    eForm.innerHTML = ''
    const fields = await getProcessorFields()
    if (!fields) return
    const allFields = fields.all
    gImageFields = fields.images

    let maxLabelChars = 0
    for (const [index, field] of Object.entries(allFields))
        if (maxLabelChars < field.length) maxLabelChars = field.length
    const labelOnLeft = maxLabelChars <= MAX_RIGHT_ALIGNED_LABEL_CHARS

    for (const [index, field] of Object.entries(allFields)) {
        if (gImageFields.includes(field)) {
            const imageField = document.createElement('span')
            if (labelOnLeft) imageField.className = 'label-on-left'
            const label = document.createElement('span')
            const avatar = document.createElement('sl-avatar')
            const icon = document.createElement('sl-icon')
            label.textContent = field
            avatar.id = field
            avatar.shape = 'rounded'
            avatar.label = label
            icon.slot = 'icon'
            icon.name = 'person-bounding-box'
            avatar.appendChild(icon)
            imageField.appendChild(label)
            if (!labelOnLeft) addLineBreak(imageField)
            imageField.appendChild(avatar)
            eForm.appendChild(imageField)
            continue
        }

        const item = document.createElement('sl-input')
        item.id = field
        if (labelOnLeft) item.className = 'label-on-left'
        item.label = field
        eForm.appendChild(item)
    }
}

function addLineBreak(element) {
    element.appendChild(document.createElement('br'))
}

async function init() {
    await initParams()
    await initElements()
    await initLocation()
    await initSamples()
}

init()
