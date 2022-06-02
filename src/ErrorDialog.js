import React from 'react';
import Button from '@material-ui/core/Button';
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import PropTypes from 'prop-types';

function ErrorDialog(props) {

  if (this.props.open) {
    console.log(`Error logging:`)
    console.dir(props.error);
  }
  return (
    <Dialog open={props.open}>
      <DialogTitle>Error</DialogTitle>
      <DialogContent>
        <DialogContentText>
          An error has been detected
          <br />
          {(!props.error && !props.error.message) ? "No Message" : props.error.message}
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button color="primary" onClick={props.onClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
} // ErrorDialog

ErrorDialog.propTypes = {
  'open': PropTypes.bool.isRequired,
  'onClose': PropTypes.func.isRequired,
  'error': PropTypes.object.isRequired
}

export default ErrorDialog;