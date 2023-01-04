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
import { Paper, Typography } from '@mui/material';

/**
 * props
 * * data - The Document object from the JSON
 */

function NoData(props) {


  return (
    <Paper sx={{flexGrow: 1, padding: "20px"}}>
      <Typography variant="h4">
      No data. 
      </Typography>

      <Typography variant="body1" component="p">
      Load a JSON document from the local file system that is the saved result of a Document AI parse output.
      </Typography>
    </Paper>
  )
} // NoData

export default NoData