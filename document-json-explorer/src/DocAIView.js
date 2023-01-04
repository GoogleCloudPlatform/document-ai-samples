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
import { useState, useEffect } from 'react';
import DrawDocument from "./DrawDocument"
import EntityInfoDialog from './EntityInfoDialog';
import PageSelector from './PageSelector';
import NoData from './NoData';
import { Box } from '@mui/material';
import PropTypes from 'prop-types';
import EntityList from './EntityList';

/**
 * props
 * * data - The Document object from the JSON
 */

function DocAIView(props) {
  const [hilight, setHilight] = useState(null);
  const [entityInfoDialogOpen, setEntityInfoDialogOpen] = useState(false);
  const [entityInfoDialogEntity, setEntityInfoDialogEntity] = useState(null);
  const [imageSize, setImageSize] = useState({width: 0, height: 0});

  function entityOnClick(entity) {
    setHilight(entity)
  }

  function onInfoClick(entity) {
    setEntityInfoDialogOpen(true);
    setEntityInfoDialogEntity(entity);
  }

  useEffect(() => {
    setImageSize({width: 0, height: 0})
  }, [props.data])

  if (!props.data) {
    return (<NoData />)
  }

  //console.dir(props.data);
  const imageData = props.data.pages[0].image.content;
  if (imageSize.width === 0 && imageSize.height === 0) {
    // We don't know the image size.  Lets find out.
    const img = document.createElement("img");
    img.onload = function (event)
    {
      console.log("natural:", img.naturalWidth, img.naturalHeight);
      console.log("width,height:", img.width, img.height);
      console.log("offsetW,offsetH:", img.offsetWidth, img.offsetHeight);
        setImageSize({width: img.width, height: img.height })
    }
    img.src=`data:image/png;base64,${imageData}`
    return <NoData/>
  }
  //const imageSize = { width: props.data.pages[0].image.width, height: props.data.pages[0].image.height }
  const drawDocument = <DrawDocument
    imageData={imageData}
    imageSize={imageSize}
    entities={props.data.entities}
    hilight={hilight}
    entityOnClick={entityOnClick} />;

  return (
    <Box sx={{ display: "flex", width: "100%", height: "100%" }}>
      <EntityList data={props.data} onInfoClick={onInfoClick} entityOnClick={entityOnClick} hilight={hilight} />
      <Box sx={{ flexGrow: 1, display: "flex", flexDirection: "row" }}>
        <Box sx={{ flexGrow: 1 }}>
          {drawDocument}
        </Box>
        <Box>
          <PageSelector data={props.data}></PageSelector>
        </Box>

      </Box>
      <EntityInfoDialog
        open={entityInfoDialogOpen}
        close={() => setEntityInfoDialogOpen(false)}
        entity={entityInfoDialogEntity}></EntityInfoDialog>
    </Box>
  )
} // DocAIView

DocAIView.propTypes = {
  'data': PropTypes.object
}

export default DocAIView