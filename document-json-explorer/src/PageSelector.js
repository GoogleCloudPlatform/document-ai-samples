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
import { Tabs, Tab, Box } from '@mui/material';
import PropTypes from 'prop-types';

const desiredImageWidth = 80   // Desired width of the mini page image
/**
 * props
 * * data - The Document object from the JSON
 * * onPageChange - A callback invoked when the page changes.
 */

/**
 * Display a vertically selectable list of pages
 * @param {*} props 
 * @returns 
 */
function PageSelector(props) {
  function pageChange(pageNumber) {
    setValue(pageNumber)
    if (props.onPageChange) {
      props.onPageChange(pageNumber)
    }
  }

  const [value, setValue] = useState(0);  // Currently selected tab (page/image)
  return (
    <Tabs value={value} TabIndicatorProps={{
      sx: {
        left: 0
      }
    }} sx={{ backgroundColor: "lightgray" }} orientation="vertical" onChange={(event, newValue) => { pageChange(newValue) }}>
      {
        props.data.pages.map((page, index) => {
          let imageData = `data:image/png;base64,${page.image.content}`
          let labelNode = <Box>
            <img src={imageData} style={{ width: `${desiredImageWidth}px` }} alt="page" />
            <br/>
            {page.pageNumber}
            </Box>
          // In a DocAI Document, the image for the document in a page is at image.content
          // 
          return <Tab key={index} label={labelNode} />
        })
      }
    </Tabs>
  )
} // PageSelector

PageSelector.propTypes = {
  'data': PropTypes.object.isRequired,
  'onPageChange': PropTypes.func
}

export default PageSelector