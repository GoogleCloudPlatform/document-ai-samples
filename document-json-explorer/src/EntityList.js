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
import { useEffect } from 'react';
import { Box } from '@mui/material';
import Entity from './Entity';
import PropTypes from 'prop-types';

/**
 * props
 * * data - The Document object from the JSON
 * * onInfoClick - Callback when clicked
 * * onClick - Callback when clicked
 * * hilight - Which item to hilight
 */

function EntityList(props) {
  useEffect(() => {
    console.log("EntityList hilight changed")
  }, [props.hilight])

  return (
    <Box sx={{ height: "100%", width: "300px", overflowY: "auto" }}>
      {
        // We get the entities and then copy them into a new array.
        // We next sort the array.  Since the sorting is in place and
        // we don't want to update the original document, that is why 
        // we take a copy of the array in the first place.
        props.data.entities.slice().sort((a, b) => {
          if (a.type > b.type) return 1;
          if (a.type < b.type) return -1;
          return 0;
        }).map(entity => {
          return (
            <Entity
              key={entity.id}
              entity={entity}
              hilight={props.hilight}
              onInfoClick={props.onInfoClick}
              onClick={props.entityOnClick} />
          )
        })
      }
    </Box>
  )
} // EntityList



EntityList.propTypes = {
  'onInfoClick': PropTypes.func.isRequired,
  'entityOnClick': PropTypes.func.isRequired,
  'hilight': PropTypes.object,
  'data': PropTypes.object.isRequired
}

export default EntityList