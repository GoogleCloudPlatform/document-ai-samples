import React from 'react';
import Dialog from '@mui/material/Dialog';
import { Button, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import PropTypes from 'prop-types';
/**
 * props
 * * open - Set to true to open the dialog
 * * entity - The entity to show
 * * close - Callback when the dialog is closed
*/

function EntityInfoDialog(props) {

  function handleClose() {
    props.close();
  }
  if (props.entity === null) {
    return null
  }
  return (
    <Dialog open={props.open} fullWidth>
      <DialogTitle>Entity Details: {props.entity.type}</DialogTitle>
      <DialogContent dividers>
        <pre style={{ width: "100%", overflowX: "auto" }}>{JSON.stringify(props.entity, null, 2)}</pre>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
} // EntityInfoDialog

EntityInfoDialog.propTypes = {
  'open': PropTypes.bool,
  'close': PropTypes.func,
  'entity': PropTypes.object,
}

export default EntityInfoDialog