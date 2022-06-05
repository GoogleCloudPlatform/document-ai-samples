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
import { useState } from 'react';
import { Tabs, Tab } from '@mui/material';
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
  const [value, setValue] = useState(0);  // Currently selected tab (page/image)
  return (
    <Tabs value={value} TabIndicatorProps={{
      sx: {
        left: 0
      }
    }} sx={{ backgroundColor: "lightgray" }} orientation="vertical" onChange={(event, newValue) => { setValue(newValue) }}>
      {
        props.data.document.entities.map(entity => {
          let x = (
            <Entity
              entity={entity}
              hilight={props.hilight}
              onInfoClick={props.onInfoClick}
              onClick={props.entityOnClick} />
          )
          return <Tab label={x} />
        })
      }
    </Tabs>
  )
} // EntityList

EntityList.propTypes = {
  'onInfoClick': PropTypes.func.isRequired,
  'onClick': PropTypes.func.isRequired,
  'hilight': PropTypes.object,
  'data': PropTypes.object.isRequired
}

export default EntityList