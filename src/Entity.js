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
import InfoIcon from '@mui/icons-material/Info';
import React, { useEffect } from 'react';
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

  const cardRef = React.createRef(); // Create a ref for the containing card so that we can scroll it into view

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

  // When the entity has rendered, if this entity is hilighted, then scroll it into
  // view within the containing list.
  useEffect(() => {
    if (hilight) {
      cardRef.current.scrollIntoView();
    }
  })

  return (
    <Card ref={cardRef} variant="outlined" style={{ backgroundColor: hilight ? "lightgray" : "white", margin: "4px" }} onClick={onClick}>
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