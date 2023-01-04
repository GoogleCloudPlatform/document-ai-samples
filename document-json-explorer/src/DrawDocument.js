/*
# Copyright 2022, Google, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/

/**
 * Draw the document.
 * 
 * Draw the document that is supplied by the imageData property.  The size of the image is
 * supplied by the imageSize property which is a {width, height}.
 * 
 * In addition to drawing the image, the entities supplied in the entities property are
 * drawn as overlays on the image.
 * 
 * From an implementation standpoint, we use the ReactSVGPanZoom module to act as a container for
 * the SVG.  This adds a wealth of goodies including pan and zoom.  Contained within we create
 * an SVG container that contains an SVG image use to display the document image.  We have a
 * helper React component called EntityHilight that draws a hilight around each of the entities
 * in the SVG.
 * 
 * Possibly one of the trickiest things in this module is handling sizing of the SVG and the image.
 * We have two primary tricks.  The first is that a <Box> surrounds the whole thing.  We take
 * a reference of thise box and use a hook called useEffect() which is called after the DOM
 * renders.  At THAT point the <Box> is at its "final" size.  This allows us to know at THAT
 * point what the size of the containing area will be for the SVG.  When the component initially
 * rendered we set the size of the SVG to be (10,10) and saved that in state.  This is very
 * small.  When the DOM initiall renders and THEN we know the final size of the container, we
 * change the SVG size to fill the container.  This re-renders and now we are at full size.
 * 
 * DocAIView is the primary consumer of this component.
 */
import { Box } from '@mui/material';
import EntityHilight from './EntityHilight';
import { useRef, useState, useEffect } from 'react';
import { INITIAL_VALUE, ReactSVGPanZoom, TOOL_NONE, POSITION_NONE } from 'react-svg-pan-zoom';
import { imageScale } from "./utils"
import PropTypes from 'prop-types';

/**
 * Props:
 * * imageData - The image data to show in the viewer
 * * imageSize - {width, height} of the image
 * * entityOnClick - A callback to be invoked when the entity is clicked
 * * hilight - The entity to hilight
 * * entities - The set of entities to display
 */


/**
 * A debounce wrapper that calls the passed in function after a specified number
 * of milliseconds.  If the debouncer is called a second time berfore the timer
 * has fired, the original timer will be cancelled and a new one started.  This
 * means that if the debounced function is called repeatedly, only one instance
 * will be finally invoked
 * @param {*} fn The function to be called
 * @param {*} ms The number of milliseconds to pass before the function is called.
 * @returns N/A
 */

let timer
function debounce(fn, ms) {
  return _ => {
    clearTimeout(timer)
    timer = setTimeout(_ => {
      timer = null
      fn.apply(this, arguments)
    }, ms)
  };
}

function DrawDocument(props) {
  const minSize = {width: 10, height: 10}
  const viewerRef = useRef(null);
  const ref1 = useRef(null);
  const [tool, setTool] = useState(TOOL_NONE)
  const [value, setValue] = useState(INITIAL_VALUE)
  const [svgContainerSize, setSvgContainerSize] = useState(minSize)


  // When the Dom has rendered, fit the SVG to viewer.
  useEffect(() => {
    if (viewerRef.current) {
      viewerRef.current.fitToViewer();
    }
  }, []);

  // Handle a calculation of the container size.
  useEffect(() => {

    if (ref1.current) {
      const br = ref1.current.getBoundingClientRect();
      const w = ref1.current.offsetWidth
      const h = ref1.current.offsetHeight
      console.log(`useEffect: NewSize:: ${w}x${h}, currentSize: ${svgContainerSize.width}x${svgContainerSize.height} ${JSON.stringify(br)}`)
      if (w !== svgContainerSize.width || h !== svgContainerSize.height) {
        setSvgContainerSize({ width: w, height: h })
      }
    }
  }, [svgContainerSize.width, svgContainerSize.height])

  // Handle a window resize.
  useEffect(() => {
    //console.log("Resize handler added!")
    
    const debouncedHandleResize = debounce(function handleResize() {
      /*
      if (ref1.current) {
        const w = ref1.current.offsetWidth
        const h = ref1.current.offsetHeight
        //console.log(`Resize:: ${w}x${h}`)
      }
      */
      //setRefreshState(refreshState+1)

      //console.log(`Setting the size to ${minSize.width}x${minSize.height}`)
      setSvgContainerSize(minSize) // The window has resized.  Set the Svg size to something small that will force a resize.
    }, 1000)

    //console.log("Adding window resize handler")
    window.addEventListener('resize', debouncedHandleResize)

    return () => {
      //console.log("Removing window resize handler")
      window.removeEventListener('resize', debouncedHandleResize)
    }
  }, [minSize])


  /**
   * Invoked when an entity on the SVG is cliecked.
   * @param {*} entity The entity that was clicked.
   * @param {*} evt 
   */
  function entityClick(entity, evt) {
    if (props.entityOnClick) {
      props.entityOnClick(entity)
    }
  }
  // Determine the optimal size of the image

  /**
   * Image an image that is 600x800 (imageWidth x imageHeight)
   * Image a viewport that is 100x100 (viewWidth x viewHeight)
   * What should the image size be?
   * Well, the height of the image should be 100 as that would maximize the image height
   * But what of the width?  It should be 600 x whatever we scaled the height.  The height scalled from 800->100.
   * This is a multiplier of (viewHeight/imageHeight)
   */
  const imageSize = imageScale(svgContainerSize, props.imageSize)
  const imageSizeSmaller = {width: Math.max(imageSize.width-10,0), height: Math.max(imageSize.height-10,0), x: imageSize.x +5, y: imageSize.y +5}
  return (
    <Box ref={ref1} style={{ flexGrow: 1, flexShrink: 1, width: "100%", height: "100%", backgroundColor: "purple", overflow: "hidden" }}>
      <ReactSVGPanZoom
        ref={viewerRef}
        miniatureProps={{ position: POSITION_NONE }}
        SVGBackground="none"
        detectAutoPan={false}
        width={svgContainerSize.width} height={svgContainerSize.height}
        tool={tool} onChangeTool={setTool}
        value={value} onChangeValue={setValue}
        onClick={event => console.log('click', event.x, event.y, event.originalEvent)}
      >
        <svg xmlns="http://www.w3.org/2000/svg"
          width={imageSize.width} height={imageSize.height}
          style={{ borderColor: "lightgrey", borderStyle: "solid", "borderWidth": "1px" }}>
          <image
            width={imageSizeSmaller.width} height={imageSizeSmaller.height}
            x={imageSizeSmaller.x} y={imageSizeSmaller.y}
            href={`data:image/png;base64,${props.imageData}`}
          />
          {
            // Draw an entity (an SVG Polygon) hilighter for each of the entities that we find.
            props.entities.map(entity => {
              return <EntityHilight
                key={entity.id}
                imageSize={imageSizeSmaller}
                entity={entity}
                onClick={entityClick}
                hilight={props.hilight} />
            })
          }
        </svg>
      </ReactSVGPanZoom>
    </Box>
  )
} // DrawDocument

DrawDocument.propTypes = {
  'imageData': PropTypes.string.isRequired,
  'imageSize': PropTypes.object.isRequired,
  'entityOnClick': PropTypes.func,
  'hilight': PropTypes.object,
  'entities': PropTypes.array,
}

export default DrawDocument