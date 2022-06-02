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