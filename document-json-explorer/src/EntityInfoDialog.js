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