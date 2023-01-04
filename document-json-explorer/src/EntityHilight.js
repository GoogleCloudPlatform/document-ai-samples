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
import { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

/**
 * props:
 * hilight
 * imageSize
 * onClick
 * onMouseOver
 * entity
 */
function EntityHilight(props) {
  let onMouseOverCallback;
  let onClickCallback;
  if (props.onClick) {
    onClickCallback = props.onClick.bind(null, props.entity)
  }
  if (props.onMouseOver) {
    onMouseOverCallback = props.onMouseOver.bind(null, props.entity)
  }

  const polygon = useRef(null);

  useEffect(() => {
    let polygonCopy = polygon.current;
    if (onClickCallback) {
      polygon.current.addEventListener('click', onClickCallback);
    }
    if (onMouseOverCallback) {
      polygon.current.addEventListener('click', onMouseOverCallback);
    }
    return () => {
      if (onClickCallback) {
        polygonCopy.removeEventListener('click', onClickCallback);
      }
      if (onMouseOverCallback) {
        polygonCopy.removeEventListener('click', onMouseOverCallback);
      }
    }
  })

  //console.dir(this.props.entity)
  let hilight = false;
  if (props.hilight) {
    if (typeof props.hilight === "string" && props.hilight === props.entity.id) {
      hilight = true;
    } else if (typeof props.hilight === "boolean") {
      hilight = props.hilight;
    } else {
      hilight = props.entity.id === props.hilight.id
    }
  }
  let points = "";
  props.entity.pageAnchor.pageRefs[0].boundingPoly.normalizedVertices.forEach((point) => {
    if (points.length !== 0) {
      points += " "
    }
    points += `${point.x * props.imageSize.width + props.imageSize.x},${point.y * props.imageSize.height + props.imageSize.y}`
  })
  let fillColor = "yellow";
  if (hilight) {
    fillColor = "blue";
  }
  return <polygon ref={polygon} points={points} fillOpacity="0.1" stroke="blue" fill={fillColor}></polygon>
} // EntityHilight

EntityHilight.propTypes = {
  'imageSize': PropTypes.object.isRequired,
  'onClick': PropTypes.func,
  'onMouseOver': PropTypes.func,
  'hilight': PropTypes.object,
  'entity': PropTypes.object,
}

export default EntityHilight