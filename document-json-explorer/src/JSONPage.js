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
//import { useState, useEffect, useRef } from 'react';
import { Box, Card } from '@mui/material';
import NoData from './NoData';
import PropTypes from 'prop-types';

/**
 * props
 * * data - The Document object from the JSON
 */

function JSONPage(props) {

  if (props.data === null) {
    return <NoData></NoData>
  }
  return (
    <Box sx={{ flexGrow: 1, overflowY: "auto" }}>
      <Card variant='outlined' sx={{ margin: "4px", height: "inherit" }}>
        {
          <pre>{JSON.stringify(props.data, null, 2)}</pre>
        }
      </Card>
    </Box>
  )
} // JSONPage

JSONPage.propTypes = {
  'data': PropTypes.object.isRequired
}

export default JSONPage