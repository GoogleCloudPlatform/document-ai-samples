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