import InfoIcon from '@mui/icons-material/Info';
import React from 'react';
import { CardHeader, Card, CardContent, IconButton, Typography } from '@mui/material';
import PropTypes from 'prop-types';

/**
 * Display an Entity card for a given entity.
 * props
 * * entity - The entity to display
 * * hilight
 * * onClick - A callback invoked when the card is clicked.
 * * onInfoClick - A callback invoked when the Info icon is clicked.
 */
function Entity(props) {

  function onClick() {
    if (props.onClick) {
      props.onClick(props.entity);
    }
  }

  function onInfoClick(event) {
    event.stopPropagation();
    if (props.onInfoClick) {
      props.onInfoClick(props.entity);
    }
  }

  // Determine whether or not we should hilight.  The rules are:
  // If no hilight is supplied then no hilight
  // If a string, then compare it to the enetity id value
  // If a boolean, then hilight based on the value of the boolean
  // If an object, assume it is an entity and hilight based on the id comparison
  //
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

  return (
    <Card variant="outlined" style={{ backgroundColor: hilight ? "lightgray" : "white", margin: "4px" }} onClick={onClick}>
      <CardHeader
        title={props.entity.type}
        action={props.onInfoClick &&
          <IconButton
            color="primary"
            size="small"
            onClick={onInfoClick}>
            <InfoIcon />
          </IconButton>
        }>
      </CardHeader>
      <CardContent>
        <Typography variant="body1">
          Text: {props.entity.mentionText}
          <br />
          Confidence: {props.entity.confidence}
        </Typography>
      </CardContent>
    </Card>
  )
} // Entity

Entity.propTypes = {
  'onInfoClick': PropTypes.func.isRequired,
  'onClick': PropTypes.func.isRequired,
  'hilight': PropTypes.object,
  'entity': PropTypes.object.isRequired
}

export default Entity