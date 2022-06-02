import { useState } from 'react';
import Entity from "./Entity"
import DrawDocument from "./DrawDocument"
import EntityInfoDialog from './EntityInfoDialog';
import PageSelector from './PageSelector';
import { Stack, Box } from '@mui/material';
import PropTypes from 'prop-types';

/**
 * props
 * * data - The Document object from the JSON
 */

function DocAIView(props) {
  const [hilight, setHilight] = useState(null);
  const [entityInfoDialogOpen, setEntityInfoDialogOpen] = useState(false);
  const [entityInfoDialogEntity, setEntityInfoDialogEntity] = useState(null);

  function entityOnClick(entity) {
    setHilight(entity)
  }

  function onInfoClick(entity) {
    setEntityInfoDialogOpen(true);
    setEntityInfoDialogEntity(entity);
  }

  if (!props.data) {
    return (<p>No Data</p>)
  }
  //console.dir(props.data);
  const imageData = props.data.document.pages[0].image.content;
  const imageSize = { width: props.data.document.pages[0].image.width, height: props.data.document.pages[0].image.height }
  const   drawDocument = <DrawDocument
      imageData={imageData}
      imageSize={imageSize}
      entities={props.data.document.entities}
      hilight={hilight}
      entityOnClick={entityOnClick} />;

  return (

    <Box sx={{ display: "flex", width: "100%", height: "100%"}}>
      <Box sx={{ height: "100%", width: "300px", overflowY: "auto" }}>
        <Stack spacing={0}>
          {
            // We get the entities and then copy them into a new array.
            // We next sort the array.  Since the sorting is in place and
            // we don't want to update the original document, that is why 
            // we take a copy of the array in the first place.
            props.data.document.entities.slice().sort((a,b) => {
              if (a.type > b.type) return 1;
              if (a.type < b.type) return -1;
              return 0;
            }).map(entity => {
              return (
                <Entity
                  key={entity.id}
                  entity={entity}
                  hilight={hilight}
                  onInfoClick={onInfoClick}
                  onClick={entityOnClick} />
              )
            })
          }
        </Stack>
      </Box>
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